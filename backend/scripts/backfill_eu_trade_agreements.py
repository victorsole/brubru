"""
Backfill ``eu_trade_agreements`` from Cellar.

Universe: every CELEX sector-2 instrument with type letter ``A`` (i.e. the
signed agreements themselves — FTAs, EPAs, Association Agreements, PCAs,
Fisheries Partnership Agreements, Aviation Agreements, tax-info exchanges,
Exchange-of-Letters instruments). ~980 records as of May 2026.

Per record we:
  1. Pull metadata (title, document_date, work URI, available languages,
     in-force flag, EuroVoc concepts, resource type with English label) via
     the existing CellarSPARQLClient.
  2. Try Cellar XHTML manifestation in EN — if present, store as body_html
     and derive body_text via tag-strip.
  3. Fall back to Cellar PDF — extract text via pypdf; body_html stays null
     (honest contract: we never synthesise HTML from PDF text).
  4. Derive an agreement_type and partner from the title via simple regex
     (best-effort; flag remaining as 'Other').
  5. UPSERT.

Throttled at 0.6s/request. Resumable — UPSERT skips on conflict (we
overwrite metadata but only re-fetch body if currently has_body=false).

Run:
    python3.12 backend/scripts/backfill_eu_trade_agreements.py            # dry-run, 5 rows
    python3.12 backend/scripts/backfill_eu_trade_agreements.py --apply
    python3.12 backend/scripts/backfill_eu_trade_agreements.py --apply --refresh-bodies   # re-fetch bodies even if has_body
"""

from __future__ import annotations

import argparse
import asyncio
import io
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"

THROTTLE_S = 0.6
MIN_BODY_LEN = 500
CELEX_PATTERN = re.compile(r"^2\d{4}A[0-9R().]+$")  # sector 2 type A (allow corrigendum suffixes)


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


# ─────────────────────── Title classification ────────────────────────────


_TYPE_PATTERNS = [
    # Strict free-trade family
    (re.compile(r"comprehensive economic and trade", re.I), "FTA"),  # CETA
    (re.compile(r"free trade agreement", re.I), "FTA"),
    (re.compile(r"economic partnership agreement", re.I), "EPA"),
    (re.compile(r"interim agreement on trade", re.I), "InterimTrade"),
    # Association + cooperation
    (re.compile(r"association agreement", re.I), "AssociationAgreement"),
    (re.compile(r"partnership and cooperation agreement", re.I), "PCA"),
    (re.compile(r"enhanced partnership and cooperation", re.I), "EPCA"),
    (re.compile(r"strategic partnership", re.I), "StrategicPartnership"),
    # Sectoral
    (re.compile(r"sustainable fisheries partnership|fisheries partnership", re.I), "FisheriesPartnership"),
    (re.compile(r"euro-mediterranean aviation|air transport agreement|aviation agreement", re.I), "Aviation"),
    (re.compile(r"common aviation area", re.I), "Aviation"),
    (re.compile(r"horizon|research and innovation cooperation|scientific and technological cooperation", re.I), "ResearchCooperation"),
    (re.compile(r"agreement on social security", re.I), "SocialSecurity"),
    (re.compile(r"customs cooperation|administrative cooperation in customs", re.I), "CustomsCooperation"),
    (re.compile(r"automatic exchange of (financial )?account information|exchange of (financial )?information|withholding tax", re.I), "TaxInfoExchange"),
    # Other instruments
    (re.compile(r"exchange of letters", re.I), "ExchangeOfLetters"),
    (re.compile(r"protocol", re.I), "Protocol"),
    (re.compile(r"^agreement\b", re.I), "Agreement"),
]


def classify_agreement(title: Optional[str]) -> str:
    if not title:
        return "Other"
    for pat, label in _TYPE_PATTERNS:
        if pat.search(title):
            return label
    return "Other"


# Partner extraction is split into two simpler patterns (the combined one
# tripped up the regex parser when verbose-style line breaks were present).
_PARTNER_PATTERNS = [
    # "Agreement between the European Union ... and the Republic of X, ..."
    re.compile(
        r"between\s+the\s+European\s+(?:Union|Community|Atomic Energy Community)"
        r"(?:\s+and\s+its\s+Member\s+States)?,?\s+"
        r"(?:of\s+the\s+one\s+part,?\s+and\s+)?(?:the\s+)?([A-Z][^,]+?)"
        r"(?:\s*[,(]|\s+of\s+the\s+other\s+part)",
        re.I,
    ),
    # "between the European Union and Mexico on/concerning/relating to ..."
    re.compile(
        r"between\s+the\s+European\s+(?:Union|Community)\s+and\s+"
        r"(?:the\s+)?([A-Z][^,]+?)(?:\s+(?:on|concerning|establishing|relating))",
        re.I,
    ),
]


def extract_partner(title: Optional[str]) -> Optional[str]:
    if not title:
        return None
    for pat in _PARTNER_PATTERNS:
        m = pat.search(title)
        if not m:
            continue
        raw = m.group(1).strip()
        raw = re.sub(r"\s+of\s+the\s+(one|other)\s+part$", "", raw, flags=re.I)
        raw = raw.strip(" ,;:")
        if 0 < len(raw) <= 120:
            return raw
    return None


# ─────────────────────── Body fetch ──────────────────────────────────────


from urllib.parse import quote as _urlquote


def _cellar_url(celex: str) -> str:
    # CELEX often contains parens, e.g. 21999A1231(13) — must be URL-encoded.
    return f"https://publications.europa.eu/resource/celex/{_urlquote(celex, safe='')}"


def fetch_xhtml(celex: str) -> Optional[str]:
    """Cellar XHTML manifestation. Returns HTML string or None if not available."""
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
    """Cellar PDF resource. Cellar may return HTTP 300 (multi-choice) for PDFs;
    in that case the body is a small HTML/XML listing of available PDFs and
    we have to grep for the DOC_1 (act body) URL and re-fetch."""
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
            # Cellar served a 300-multi-choice listing — find DOC_1 PDF inside.
            try:
                listing = body.decode("utf-8", errors="replace")
            except Exception:
                return None
            m = re.search(r'(https?://publications\.europa\.eu/resource/cellar/[^"\s<>]+DOC_1\.pdf)', listing)
            if not m:
                return None
            doc_url = m.group(1)
            req2 = urllib_request.Request(
                doc_url,
                headers={"Accept": "application/pdf", "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0)"},
            )
            try:
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


def extract_pdf(pdf_bytes: bytes) -> Optional[str]:
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


# ─────────────────────── Cellar metadata via SPARQL client ───────────────


async def fetch_celex_universe() -> list[dict]:
    """Pull every sector-2 type-A CELEX from Cellar via the existing client.

    Cellar's SPARQL endpoint caps at 10,000 results per query and returns
    HTTP 500 on offset >= 10000. We shard by 5-year buckets — each bucket
    has < 5,000 sector-2 rows — and paginate within each.
    """
    sys.path.insert(0, str(ROOT / "backend"))
    from services.api_clients.cellar_sparql_client import CellarSPARQLClient

    # 5-year buckets covering 1958 → today.
    buckets: list[tuple[date, date]] = []
    start_year = 1958
    end_year = 2030
    y = start_year
    while y <= end_year:
        buckets.append((date(y, 1, 1), date(min(y + 4, end_year), 12, 31)))
        y += 5

    universe: list[dict] = []
    async with CellarSPARQLClient() as client:
        for d_from, d_to in buckets:
            offset = 0
            bucket_rows = 0
            while True:
                try:
                    rows = await client.discover_by_date_range(
                        date_from=d_from, date_to=d_to,
                        sectors=["2"], language="ENG",
                        limit=1000, offset=offset,
                    )
                except Exception as exc:
                    print(f"[warn]   {d_from.year}-{d_to.year}@{offset}: {exc!s}", flush=True)
                    break
                if not rows:
                    break
                universe.extend(rows)
                bucket_rows += len(rows)
                if len(rows) < 1000:
                    break
                offset += 1000
                if offset >= 10000:  # safety — should never hit with 5y buckets
                    break
            print(f"[INFO]   bucket {d_from.year}-{d_to.year}: {bucket_rows:>5} rows", flush=True)

    # Dedup by celex + filter to type-A (signed agreements)
    by_celex: dict[str, dict] = {}
    for r in universe:
        celex = r.get("celex") or ""
        if not CELEX_PATTERN.match(celex):
            continue
        existing = by_celex.get(celex)
        if existing and (r.get("title") or "") and not (existing.get("title") or ""):
            by_celex[celex] = r
        elif not existing:
            by_celex[celex] = r
    return list(by_celex.values())


async def hydrate_metadata(celex: str) -> dict:
    """Cellar metadata + languages + EuroVoc + resource-type label."""
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
INSERT INTO eu_trade_agreements (
    celex, work_uri, title, document_date,
    resource_type_uri, resource_type_label,
    agreement_type, partner,
    in_force, date_in_force, date_end_validity,
    available_languages, eurovoc_concepts,
    eurlex_url,
    has_body, body_html, body_text, body_source,
    fetched_at, updated_at
) VALUES (
    %(celex)s, %(work_uri)s, %(title)s, %(document_date)s,
    %(resource_type_uri)s, %(resource_type_label)s,
    %(agreement_type)s, %(partner)s,
    %(in_force)s, %(date_in_force)s, %(date_end_validity)s,
    %(available_languages)s, %(eurovoc_concepts)s,
    %(eurlex_url)s,
    %(has_body)s, %(body_html)s, %(body_text)s, %(body_source)s,
    NOW(), NOW()
)
ON CONFLICT (celex) DO UPDATE SET
    work_uri = COALESCE(EXCLUDED.work_uri, eu_trade_agreements.work_uri),
    title = COALESCE(EXCLUDED.title, eu_trade_agreements.title),
    document_date = COALESCE(EXCLUDED.document_date, eu_trade_agreements.document_date),
    resource_type_uri = COALESCE(EXCLUDED.resource_type_uri, eu_trade_agreements.resource_type_uri),
    resource_type_label = COALESCE(EXCLUDED.resource_type_label, eu_trade_agreements.resource_type_label),
    agreement_type = EXCLUDED.agreement_type,
    partner = COALESCE(EXCLUDED.partner, eu_trade_agreements.partner),
    in_force = EXCLUDED.in_force,
    date_in_force = COALESCE(EXCLUDED.date_in_force, eu_trade_agreements.date_in_force),
    date_end_validity = COALESCE(EXCLUDED.date_end_validity, eu_trade_agreements.date_end_validity),
    available_languages = EXCLUDED.available_languages,
    eurovoc_concepts = EXCLUDED.eurovoc_concepts,
    eurlex_url = EXCLUDED.eurlex_url,
    -- Body fields: only overwrite when the new fetch actually produced a body
    has_body = CASE WHEN EXCLUDED.has_body THEN EXCLUDED.has_body ELSE eu_trade_agreements.has_body END,
    body_html = CASE WHEN EXCLUDED.has_body THEN EXCLUDED.body_html ELSE eu_trade_agreements.body_html END,
    body_text = CASE WHEN EXCLUDED.has_body THEN EXCLUDED.body_text ELSE eu_trade_agreements.body_text END,
    body_source = CASE WHEN EXCLUDED.has_body THEN EXCLUDED.body_source ELSE eu_trade_agreements.body_source END,
    fetched_at = CASE WHEN EXCLUDED.has_body THEN NOW() ELSE eu_trade_agreements.fetched_at END,
    updated_at = NOW();
"""


def to_iso(value: Any) -> Optional[str]:
    if not value:
        return None
    s = str(value).split("T")[0]
    return s if re.match(r"^\d{4}-\d{2}-\d{2}$", s) else None


# ─────────────────────── Main ────────────────────────────────────────────


def _open_db():
    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing", file=sys.stderr)
        sys.exit(1)
    conn = psycopg2.connect(db, connect_timeout=15)
    return conn


async def main_async(args):
    print("[INFO] Listing sector-2 type-A CELEX universe via Cellar SPARQL...", flush=True)
    universe = await fetch_celex_universe()
    print(f"[INFO] {len(universe):,} type-A signed agreements", flush=True)

    # Open Postgres AFTER the long SPARQL phase so the pooler doesn't expire.
    conn = _open_db()
    cur = conn.cursor()

    # Determine which already have body (skip body-fetch if not refreshing)
    cur.execute("SELECT celex, has_body FROM eu_trade_agreements")
    existing = {row[0]: bool(row[1]) for row in cur.fetchall()}

    if not args.apply:
        universe = universe[: args.limit]

    counts = {"upserted": 0, "body_xhtml": 0, "body_pdf": 0, "no_body": 0, "errors": 0}
    for i, row in enumerate(universe, 1):
        celex = row["celex"]

        # Refresh metadata always.
        try:
            meta = await hydrate_metadata(celex)
        except Exception as exc:
            print(f"  [{i:4}/{len(universe)}] {celex}: meta error {exc!s}", flush=True)
            counts["errors"] += 1
            continue

        title = meta.get("title") or row.get("title")
        agreement_type = classify_agreement(title)
        partner = extract_partner(title)

        # Body fetch (only if missing or --refresh-bodies)
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
                    text = extract_pdf(pdf) or ""
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
            "title": title,
            "document_date": to_iso(meta.get("document_date") or row.get("date")),
            "resource_type_uri": meta.get("resource_type_uri"),
            "resource_type_label": meta.get("resource_type_label"),
            "agreement_type": agreement_type,
            "partner": partner,
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
                    # Pooler dropped the conn. Reopen once and retry.
                    if attempt >= 2:
                        counts["errors"] += 1
                        print(f"  [{i:4}] dropped conn unrecoverable on {celex}: {exc!s}", flush=True)
                        break
                    attempt += 1
                    print(f"  [{i:4}] reopening pooled conn (attempt {attempt}) ...", flush=True)
                    try:
                        cur.close(); conn.close()
                    except Exception:
                        pass
                    conn = _open_db()
                    cur = conn.cursor()
                except Exception as exc:
                    conn.rollback()
                    counts["errors"] += 1
                    print(f"  [{i:4}] DB error on {celex}: {exc!s}", flush=True)
                    break
        else:
            print(f"  [{i:4}] {celex} | {agreement_type:18} | partner={partner or '—'} | "
                  f"body={'+' if has_body else '—'}({body_source or 'n/a'}) "
                  f"title={(title or '')[:60]}", flush=True)

    if args.apply:
        conn.commit()

    print()
    print(f"[DONE] {counts}{' (DRY)' if not args.apply else ''}")
    cur.close()
    conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--throttle", type=float, default=THROTTLE_S)
    ap.add_argument("--refresh-bodies", action="store_true",
                    help="Re-fetch body even if has_body=true (overrides cache)")
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
