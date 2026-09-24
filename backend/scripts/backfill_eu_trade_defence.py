"""
Backfill ``eu_trade_defence_measures`` from Cellar.

Universe: every CELEX sector-3 type-R regulation whose title matches the
trade-defence keyword set (anti-dumping / countervailing / safeguard /
compensatory / undertaking / registration of imports). Per match we:

  1. Pull metadata (title, dates, work URI, languages, in-force flag,
     EuroVoc concepts, resource-type label) via the Cellar SPARQL client.
  2. Fetch the regulation body via Cellar XHTML, fall back to PDF.
  3. Classify measure_type / duty_status / target_country / product from
     the title (deterministic regex; "Other" when nothing matches).
  4. UPSERT into eu_trade_defence_measures.

Throttle 0.6s/request. Resumable — UPSERT skips already-bodied rows
unless --refresh-bodies is passed.

Run:
    python3.12 backend/scripts/backfill_eu_trade_defence.py            # dry-run, 5 rows
    python3.12 backend/scripts/backfill_eu_trade_defence.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import io
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import quote as _urlquote

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"

THROTTLE_S = 0.6
MIN_BODY_LEN = 500


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


# ─────────────────────── Title classification ────────────────────────────


_KEYWORDS = re.compile(
    r"\b(anti-?dumping|countervailing|safeguard\s+measure|compensatory\s+dut|"
    r"definitive\s+anti-?dumping|provisional\s+anti-?dumping|registration\s+of\s+imports)\b",
    re.IGNORECASE,
)


def is_trade_defence(title: Optional[str]) -> bool:
    if not title:
        return False
    return bool(_KEYWORDS.search(title))


def classify_measure_type(title: str) -> str:
    t = title.lower()
    # Order matters — pick most-specific first.
    if "anti-dumping" in t or "antidumping" in t:
        return "anti_dumping"
    if "countervailing" in t or "compensatory dut" in t:
        return "countervailing"
    if "safeguard measure" in t or "safeguard" in t:
        return "safeguard"
    if "registration of imports" in t:
        return "registration"
    return "other"


_INITIATING = re.compile(r"\binitiating (?:a|an|the)\b", re.IGNORECASE)


def classify_duty_status(title: str) -> str:
    t = title.lower()
    # An act that OPENS a proceeding is an initiation, whether what it opens is an
    # investigation or a review: "initiating a 'new exporter' review" matched neither
    # phrasing below and, because these acts also order registration of the imports
    # concerned, 53 of them were about to be labelled "registration" -- the ancillary
    # step, not what the act does.
    if _INITIATING.search(t) or "initiation" in t:
        return "initiation"
    # "making imports of X ... subject to registration" is the phrasing every
    # registration regulation uses in 2026 (2026/1747, 1824, 2022, 2023, 2049);
    # only "registration of imports" was recognised, so they classified "other".
    if "registration of imports" in t or "subject to registration" in t:
        return "registration"
    if "expiry review" in t or "expiry" in t:
        return "expiry_review"
    if "interim review" in t or "partial interim" in t:
        return "interim_review"
    if "review" in t:
        return "review"
    if "definitive anti-dumping" in t or "definitive countervailing" in t or "imposing a definitive" in t:
        return "definitive"
    if "provisional anti-dumping" in t or "provisional countervailing" in t or "imposing a provisional" in t:
        return "provisional"
    if "terminating" in t:
        return "termination"
    if "amending" in t or "amendment" in t:
        return "amendment"
    if "suspension" in t or "suspending" in t:
        return "suspension"
    return "other"


# Country/region extraction — anti-dumping regulations have a canonical phrase:
#   "imports of <product> originating in <country>"
_TARGET_PATTERN = re.compile(
    r"originating in (?:the\s+)?(.+?)(?:\s+(?:and|,|\.)|\Z|;)",
    re.IGNORECASE,
)
_PRODUCT_PATTERN = re.compile(
    r"imports of\s+(.+?)\s+originating in",
    re.IGNORECASE,
)


# The lazy match above runs to "and"/end-of-title, so it swallowed the rest of
# the title whenever the country was followed by a clause: measured 15 Sep 2026,
# 497 of 1,500 rows held values like "People's Republic of China following an
# expiry review pursuant to Article 11(2)..." or "...China subject to
# registration with a view to allowing the levy of anti-dumping duties". Cut at
# the first clause marker. Commas stay, so country LISTS survive.
_TARGET_CLAUSE_CUT = re.compile(
    r"\s+(?:following|subject to|by |from the extension|as regards|or not|as well as|for (?:one|two|three|four|five|\w+) (?:\w+ )?exporting|for the period|for one|for certain|for a|by imports|"
    r"to imports|as extended|as amended|with regard|with a view|pursuant|in so far|insofar|"
    r"after|and (?:terminating|repealing|collecting|definitively|amending|extending|imposing))\b"
    r"|,\s*(?:re-?)?(?:imposing|repealing|terminating|amending|and|following|as|for|manufactured|produced)\b"
    r"|,\s*\((?:EEC|EC|EU|Euratom)\)",
    re.IGNORECASE,
)

# The OJ writes "People's Republic of China" with a curly apostrophe (U+2019) in
# some acts and a straight one in others -- 403 rows against 312 on 24 Sep 2026.
# Stored as they come, the same country is two countries, and a filter on the
# straight spelling returns 312 of 715 measures while looking complete. The
# stored TITLE stays as published; only the extracted fields are normalised.
_CURLY = {0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"', 0x2032: "'"}


def normalise_quotes(value: str) -> str:
    return value.translate(_CURLY)


def extract_target_country(title: str) -> Optional[str]:
    m = _TARGET_PATTERN.search(title)
    if not m:
        return None
    raw = m.group(1).strip()
    raw = re.sub(r"^(?:or consigned from|and consigned from)\s+(?:the\s+)?", "", raw, flags=re.IGNORECASE)
    cut = _TARGET_CLAUSE_CUT.search(raw)
    if cut:
        raw = raw[: cut.start()]
    raw = re.sub(r"\s*\(.*\)\s*$", "", raw)
    raw = normalise_quotes(raw).strip(" ,;:.")
    return raw[:120] if raw else None


def extract_product(title: str) -> Optional[str]:
    m = _PRODUCT_PATTERN.search(title)
    if not m:
        return None
    raw = normalise_quotes(m.group(1).strip())
    return raw[:300] if raw else None


# ─────────────────────── Body fetch (shared with FTA pattern) ────────────


def _cellar_url(celex: str) -> str:
    return f"https://publications.europa.eu/resource/celex/{_urlquote(celex, safe='')}"


def fetch_xhtml(celex: str) -> Optional[str]:
    req = urllib_request.Request(
        _cellar_url(celex),
        headers={
            "Accept": "application/xhtml+xml",
            "Accept-Language": "en",
            "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0)",
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=30) as r:
            ctype = r.headers.get("Content-Type", "").lower()
            body = r.read()
            if "xhtml" in ctype or "html" in ctype:
                return body.decode("utf-8", errors="replace")
            return None
    except (urllib_error.HTTPError, urllib_error.URLError):
        return None
    except Exception:
        return None


def fetch_pdf(celex: str) -> Optional[bytes]:
    req = urllib_request.Request(
        _cellar_url(celex),
        headers={
            "Accept": "application/pdf",
            "Accept-Language": "en",
            "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0)",
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=45) as r:
            ctype = r.headers.get("Content-Type", "").lower()
            body = r.read()
            if "pdf" in ctype:
                return body
            try:
                listing = body.decode("utf-8", errors="replace")
            except Exception:
                return None
            m = re.search(r'(https?://publications\.europa\.eu/resource/cellar/[^"\s<>]+DOC_1\.pdf)', listing)
            if not m:
                return None
            try:
                req2 = urllib_request.Request(m.group(1),
                    headers={"Accept": "application/pdf", "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0)"})
                with urllib_request.urlopen(req2, timeout=60) as r2:
                    if "pdf" in (r2.headers.get("Content-Type") or "").lower():
                        return r2.read()
            except Exception:
                return None
            return None
    except (urllib_error.HTTPError, urllib_error.URLError):
        return None
    except Exception:
        return None


def extract_pdf_text(pdf_bytes: bytes) -> Optional[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader  # type: ignore
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n\n".join((p.extract_text() or "") for p in reader.pages).strip() or None
    except Exception:
        return None


def strip_html_to_text(html: str) -> str:
    text = re.sub(r"<(script|style|nav|footer|header|aside|form)[^>]*>.*?</\1>",
                  " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"</(p|div|li|h[1-6]|article|section|tr)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&#39;", "'"))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*\n+", "\n\n", text)
    return text.strip()


# ─────────────────────── Universe enumeration ────────────────────────────


def discovery_windows(days: Optional[int], today: Optional[date] = None) -> list[tuple[date, date, str]]:
    """Date windows to list from Cellar.

    Full walk: one bucket per year, 1995 to the CURRENT year (was a hardcoded
    range(1995, 2027), which would silently stop discovering acts on 1 Jan 2027).

    Delta (``days``): a single window ending today. Added 15 Sep 2026: before it
    the weekly cron (`--apply --limit 20`) re-walked every year from 1995 and
    re-hydrated all ~1,500 known acts oldest-first, because `--limit` only applies
    to a dry run. Inside its 1,800 s timeout it never reached 2026, so the table
    stopped at 12 May 2026 while Cellar held dozens of newer measures
    (e.g. 2026/2049, alkaline batteries registration, 14 Sep 2026).
    """
    today = today or date.today()
    if days:
        start = today - timedelta(days=days)
        return [(start, today, f"{start}..{today}")]
    return [(date(y, 1, 1), date(y, 12, 31), str(y)) for y in range(1995, today.year + 1)]


async def fetch_trade_defence_universe(days: Optional[int] = None) -> list[dict]:
    """All sector-3 regulations with trade-defence keywords in their title.

    Cellar's 10k cap is a real constraint here — sector-3 has 250k+ rows
    so we shard by 1-year buckets back to 1995 (the year the Anti-Dumping
    Regulation 384/96 came into effect, predecessor to 1225/2009 → 2016/1036).
    With ``days`` only the recent window is listed (the delta).
    """
    sys.path.insert(0, str(ROOT / "backend"))
    from services.api_clients.cellar_sparql_client import CellarSPARQLClient

    matches: list[dict] = []
    seen: set[str] = set()
    async with CellarSPARQLClient() as client:
        for w_from, w_to, label in discovery_windows(days):
            offset = 0
            year_match = 0  # init before the loop so exception path is safe
            while True:
                try:
                    rows = await client.discover_by_date_range(
                        date_from=w_from, date_to=w_to,
                        sectors=["3"], language="ENG",
                        limit=1000, offset=offset,
                    )
                except Exception as exc:
                    print(f"[warn]   {label}@{offset}: {exc!s}", flush=True)
                    break
                if not rows:
                    break
                for r in rows:
                    if not is_trade_defence(r.get("title")):
                        continue
                    celex = r.get("celex") or ""
                    if celex in seen:
                        continue
                    # Sector-3 type-R only (skip sector-3 type-D decisions)
                    if not re.match(r"^3\d{4}R\d+", celex):
                        continue
                    seen.add(celex)
                    matches.append(r)
                    year_match += 1
                if len(rows) < 1000:
                    break
                offset += 1000
                if offset >= 10000:
                    break
            print(f"[INFO]   {label}: +{year_match} trade-defence matches (running total {len(matches)})", flush=True)
    return matches


async def hydrate_metadata(celex: str) -> dict:
    sys.path.insert(0, str(ROOT / "backend"))
    from services.api_clients.cellar_sparql_client import CellarSPARQLClient
    async with CellarSPARQLClient() as c:
        meta = await c.get_celex_metadata(celex, language="ENG") or {}
        languages = await c.get_available_languages(celex) or []
        eurovoc = await c.get_eurovoc_concepts(celex) or []
        type_label = None
        if meta.get("resourceTypeUri"):
            try:
                type_label = await c.resolve_resource_type(meta["resourceTypeUri"])
            except Exception:
                type_label = None
    return {
        "title": meta.get("title"),
        "document_date": meta.get("date"),
        "work_uri": meta.get("work"),
        "in_force": bool(meta.get("inForce", False)),
        "date_in_force": meta.get("dateInForce"),
        "date_end_validity": meta.get("dateEndValidity"),
        "resource_type_uri": meta.get("resourceTypeUri"),
        "resource_type_label": type_label,
        "available_languages": languages,
        "eurovoc_concepts": eurovoc,
    }


# ─────────────────────── DB UPSERT ───────────────────────────────────────


UPSERT_SQL = """
INSERT INTO eu_trade_defence_measures (
    celex, work_uri, title, document_date,
    measure_type, duty_status, target_country, product,
    resource_type_uri, resource_type_label,
    in_force, date_in_force, date_end_validity,
    available_languages, eurovoc_concepts,
    eurlex_url,
    has_body, body_html, body_text, body_source,
    fetched_at, updated_at
) VALUES (
    %(celex)s, %(work_uri)s, %(title)s, %(document_date)s,
    %(measure_type)s, %(duty_status)s, %(target_country)s, %(product)s,
    %(resource_type_uri)s, %(resource_type_label)s,
    %(in_force)s, %(date_in_force)s, %(date_end_validity)s,
    %(available_languages)s, %(eurovoc_concepts)s,
    %(eurlex_url)s,
    %(has_body)s, %(body_html)s, %(body_text)s, %(body_source)s,
    NOW(), NOW()
)
ON CONFLICT (celex) DO UPDATE SET
    work_uri = COALESCE(EXCLUDED.work_uri, eu_trade_defence_measures.work_uri),
    title = COALESCE(EXCLUDED.title, eu_trade_defence_measures.title),
    document_date = COALESCE(EXCLUDED.document_date, eu_trade_defence_measures.document_date),
    measure_type = EXCLUDED.measure_type,
    duty_status = EXCLUDED.duty_status,
    target_country = COALESCE(EXCLUDED.target_country, eu_trade_defence_measures.target_country),
    product = COALESCE(EXCLUDED.product, eu_trade_defence_measures.product),
    resource_type_uri = COALESCE(EXCLUDED.resource_type_uri, eu_trade_defence_measures.resource_type_uri),
    resource_type_label = COALESCE(EXCLUDED.resource_type_label, eu_trade_defence_measures.resource_type_label),
    in_force = EXCLUDED.in_force,
    date_in_force = COALESCE(EXCLUDED.date_in_force, eu_trade_defence_measures.date_in_force),
    date_end_validity = COALESCE(EXCLUDED.date_end_validity, eu_trade_defence_measures.date_end_validity),
    available_languages = EXCLUDED.available_languages,
    eurovoc_concepts = EXCLUDED.eurovoc_concepts,
    eurlex_url = EXCLUDED.eurlex_url,
    has_body = CASE WHEN EXCLUDED.has_body THEN EXCLUDED.has_body ELSE eu_trade_defence_measures.has_body END,
    body_html = CASE WHEN EXCLUDED.has_body THEN EXCLUDED.body_html ELSE eu_trade_defence_measures.body_html END,
    body_text = CASE WHEN EXCLUDED.has_body THEN EXCLUDED.body_text ELSE eu_trade_defence_measures.body_text END,
    body_source = CASE WHEN EXCLUDED.has_body THEN EXCLUDED.body_source ELSE eu_trade_defence_measures.body_source END,
    fetched_at = CASE WHEN EXCLUDED.has_body THEN NOW() ELSE eu_trade_defence_measures.fetched_at END,
    updated_at = NOW();
"""


def to_iso(value: Any) -> Optional[str]:
    if not value:
        return None
    s = str(value).split("T")[0]
    return s if re.match(r"^\d{4}-\d{2}-\d{2}$", s) else None


def _open_db():
    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing", file=sys.stderr); sys.exit(1)
    return psycopg2.connect(db, connect_timeout=15)


# ─────────────────────── Main ────────────────────────────────────────────


async def main_async(args):
    _started_monotonic = time.monotonic()
    if args.fill_missing_bodies:
        # The weekly cron runs `--apply --days 21`, so it only ever hydrates acts
        # published in the last three weeks. Everything older that was listed but never
        # hydrated stays without a body for good: 977 of 1,528 measures on 24 September
        # 2026, which is what an endpoint serving "the act" has to answer from. A full
        # 1995-now walk is about nine hours, far past any cron window, so this mode
        # drains the backlog a bounded slice at a time, newest first, and is resumable
        # by construction: a row leaves the queue when it gets a body.
        conn = _open_db(); cur = conn.cursor()
        cur.execute(
            "SELECT celex, title, document_date FROM eu_trade_defence_measures "
            "WHERE has_body IS NOT TRUE ORDER BY document_date DESC NULLS LAST LIMIT %s",
            (args.fill_missing_bodies,))
        rows = cur.fetchall()
        cur.execute("SELECT count(*) FROM eu_trade_defence_measures WHERE has_body IS NOT TRUE")
        remaining = cur.fetchone()[0]
        universe = [{"celex": r[0], "title": r[1], "date": r[2]} for r in rows]
        existing = {r[0]: False for r in rows}
        print(f"[INFO] body backfill: {len(universe)} of {remaining:,} measures without a body",
              flush=True)
    else:
        print("[INFO] Listing trade-defence universe via Cellar SPARQL...", flush=True)
        universe = await fetch_trade_defence_universe(days=args.days)
        print(f"[INFO] {len(universe):,} trade-defence regulations identified", flush=True)

        conn = _open_db(); cur = conn.cursor()
        cur.execute("SELECT celex, has_body FROM eu_trade_defence_measures")
        existing = {row[0]: bool(row[1]) for row in cur.fetchall()}

    if not args.apply:
        universe = universe[: args.limit]

    counts = {"upserted": 0, "body_xhtml": 0, "body_pdf": 0, "no_body": 0, "errors": 0}
    for i, row in enumerate(universe, 1):
        celex = row["celex"]

        # A count-based slice is sized from a measured rate, and the rate is not constant:
        # the newest acts come from Cellar XHTML in ~14s, while older ones fall back to a
        # PDF fetch plus text extraction. Overrunning is not harmless -- the caller kills
        # the process and records a timeout instead of the rows it did fetch -- so stop on
        # the clock the caller is actually holding.
        if args.max_seconds and (time.monotonic() - _started_monotonic) > args.max_seconds:
            print(f"[INFO] stopping at the {args.max_seconds}s budget after {i - 1} measure(s); "
                  f"the rest stay in the queue for the next run", flush=True)
            break

        try:
            meta = await hydrate_metadata(celex)
        except Exception as exc:
            print(f"  [{i:4}] {celex}: meta error {exc!s}", flush=True)
            counts["errors"] += 1
            continue

        title = meta.get("title") or row.get("title") or ""
        measure_type = classify_measure_type(title)
        duty_status = classify_duty_status(title)
        target_country = extract_target_country(title)
        product = extract_product(title)

        body_html: Optional[str] = None
        body_text: Optional[str] = None
        body_source: Optional[str] = None
        has_body = False

        need_body = args.refresh_bodies or not existing.get(celex, False)
        if need_body:
            time.sleep(args.throttle if i > 1 else 0)
            xhtml = fetch_xhtml(celex)
            if xhtml and "<html" in xhtml.lower():
                body_html = xhtml.replace("\x00", "")[:5_000_000]
                body_text = strip_html_to_text(xhtml).replace("\x00", "")[:5_000_000]
                body_source = "xhtml"
                has_body = len(body_text) >= MIN_BODY_LEN
                if has_body:
                    counts["body_xhtml"] += 1
            else:
                time.sleep(args.throttle)
                pdf = fetch_pdf(celex)
                if pdf:
                    text = extract_pdf_text(pdf) or ""
                    text = text.replace("\x00", "")[:5_000_000]
                    if len(text) >= MIN_BODY_LEN:
                        body_text = text
                        body_source = "pdf"
                        has_body = True
                        counts["body_pdf"] += 1
            if not has_body:
                counts["no_body"] += 1

        params = {
            "celex": celex,
            "work_uri": meta.get("work_uri") or row.get("work"),
            "title": title or None,
            "document_date": to_iso(meta.get("document_date") or row.get("date")),
            "measure_type": measure_type,
            "duty_status": duty_status,
            "target_country": target_country,
            "product": product,
            "resource_type_uri": meta.get("resource_type_uri"),
            "resource_type_label": meta.get("resource_type_label"),
            "in_force": meta.get("in_force"),
            "date_in_force": to_iso(meta.get("date_in_force")),
            "date_end_validity": to_iso(meta.get("date_end_validity")),
            "available_languages": meta.get("available_languages") or [],
            "eurovoc_concepts": meta.get("eurovoc_concepts") or [],
            "eurlex_url": f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}",
            "has_body": has_body,
            "body_html": body_html,
            "body_text": body_text,
            "body_source": body_source,
        }

        if args.apply:
            attempt = 0
            while True:
                try:
                    cur.execute(UPSERT_SQL, params)
                    counts["upserted"] += 1
                    if counts["upserted"] % 25 == 0:
                        conn.commit()
                        print(f"  [{i:4}/{len(universe)}] {celex} | upserted={counts['upserted']:>4} "
                              f"body_xhtml={counts['body_xhtml']} body_pdf={counts['body_pdf']} "
                              f"no_body={counts['no_body']}", flush=True)
                    break
                except psycopg2.OperationalError as exc:
                    if attempt >= 2:
                        counts["errors"] += 1
                        print(f"  [{i:4}] dropped conn unrecoverable: {exc!s}", flush=True)
                        break
                    attempt += 1
                    print(f"  [{i:4}] reopening conn (attempt {attempt})", flush=True)
                    try: cur.close(); conn.close()
                    except Exception: pass
                    conn = _open_db(); cur = conn.cursor()
                except Exception as exc:
                    conn.rollback()
                    counts["errors"] += 1
                    print(f"  [{i:4}] DB error {celex}: {exc!s}", flush=True)
                    break
        else:
            print(f"  [{i:3}] {celex} | {measure_type:14} {duty_status:14} | "
                  f"target={target_country or '—'} | body={'+' if has_body else '—'}({body_source or 'n/a'})", flush=True)

    if args.apply:
        conn.commit()
    print()
    print(f"[DONE] {counts}{' (DRY)' if not args.apply else ''}")
    cur.close(); conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--throttle", type=float, default=THROTTLE_S)
    ap.add_argument("--refresh-bodies", action="store_true")
    ap.add_argument("--max-seconds", type=int, metavar="S", default=0,
                    help="Stop cleanly after S seconds, between measures. A slice sized by "
                         "COUNT assumes a fetch rate; this bounds the thing the caller "
                         "actually has, which is a timeout.")
    ap.add_argument("--fill-missing-bodies", type=int, metavar="N", default=0,
                    help="Skip the SPARQL listing: hydrate N stored measures that have no "
                         "body yet, newest first. Resumable; drains the historical backlog "
                         "the --days window can never reach.")
    ap.add_argument("--days", type=int, default=None,
                    help="Delta: only list acts dated in the last N days (default: full 1995-now walk)")
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
