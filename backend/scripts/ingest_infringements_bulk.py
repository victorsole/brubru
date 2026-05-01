"""
Bulk ingest of Commission infringement decisions from press-corner.

Direct-URL probing (the press-corner search API caps at ~20 hits per keyword).

Strategy:
  - For each IP_yy_NNNN in (range), GET /commission/presscorner/detail/en/IP_yy_NNNN.
  - Real document pages return ~19,000 bytes; SPA-shell pages (no document)
    return exactly ~18,157 bytes. Byte-size > 18,500 = real.
  - Real pages have a usable og:title meta tag.
  - If the title matches any infringement keyword, UPSERT into
    infringement_procedures with row-specific source_url and
    parsed (member_state, procedure_stage).
  - Concurrency: 6 worker threads.

Run: python3.12 backend/scripts/ingest_infringements_bulk.py [--year 26] [--from 1] [--to 1500]
"""

import argparse
import datetime as dt
import re
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def get_env(k):
    env = ROOT / ".env"
    if not env.exists():
        return ""
    for line in env.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


DETAIL_URL = "https://ec.europa.eu/commission/presscorner/detail/en/{ref}"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruInfringementBulk/1.0; +https://brubru.beresol.eu)"
SHELL_THRESHOLD = 18500  # below this = SPA shell (document doesn't exist)

INFRINGEMENT_TITLE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"refer.+to the Court",
        r"refers .+ to the",
        r"letter of formal notice",
        r"reasoned opinion",
        r"infringement",
        r"infringement procedure",
        r"calls on .+ Member State",
        r"closes infringement",
        r"complete transposition",
        r"non-compliance",
        r"failure to .+(comply|fulfil)",
    ]
]

STAGE_KEYWORDS = [
    ("letter of formal notice", "letter_of_formal_notice"),
    ("reasoned opinion", "reasoned_opinion"),
    ("refer the case to the court", "referral_to_court"),
    ("refer to the court", "referral_to_court"),
    ("decides to refer", "referral_to_court"),
    ("court of justice", "referral_to_court"),
    ("close the infringement", "closure"),
    ("closes infringement", "closure"),
    ("additional reasoned opinion", "additional_reasoned_opinion"),
    ("additional letter", "additional_letter_of_formal_notice"),
]

COUNTRY_NAMES = {
    "Austria": "AT", "Belgium": "BE", "Bulgaria": "BG", "Croatia": "HR",
    "Cyprus": "CY", "Czechia": "CZ", "Denmark": "DK", "Estonia": "EE",
    "Finland": "FI", "France": "FR", "Germany": "DE", "Greece": "EL",
    "Hungary": "HU", "Ireland": "IE", "Italy": "IT", "Latvia": "LV",
    "Lithuania": "LT", "Luxembourg": "LU", "Malta": "MT", "Netherlands": "NL",
    "Poland": "PL", "Portugal": "PT", "Romania": "RO", "Slovakia": "SK",
    "Slovenia": "SI", "Spain": "ES", "Sweden": "SE",
}


def is_infringement_title(title):
    if not title:
        return False
    return any(p.search(title) for p in INFRINGEMENT_TITLE_PATTERNS)


def detect_stage(title, summary):
    blob = f"{title or ''} {summary or ''}".lower()
    for keyword, stage in STAGE_KEYWORDS:
        if keyword in blob:
            return stage
    return None


def detect_member_state(title, summary):
    blob = f"{title or ''} {summary or ''}"
    for name, code in COUNTRY_NAMES.items():
        if re.search(rf"\b{re.escape(name)}\b", blob):
            return code
    return None


def fetch_detail(ref):
    """Returns (ref, status, body_bytes) or (ref, 0, b'')."""
    url = DETAIL_URL.format(ref=ref)
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return ref, r.status, r.read()
    except urllib.error.HTTPError as e:
        return ref, e.code, b""
    except Exception:
        return ref, 0, b""


def parse_doc(body):
    """Return (title, og_description, decision_date_iso) from press-corner HTML."""
    if not body:
        return None
    text = body.decode("utf-8", errors="replace")
    title_m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', text)
    desc_m = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', text)
    date_m = re.search(r'<meta\s+name="date"\s+content="([^"]+)"', text) or re.search(r'<meta\s+property="article:published_time"\s+content="([^"]+)"', text)
    return {
        "title": title_m.group(1).strip() if title_m else None,
        "description": desc_m.group(1).strip() if desc_m else None,
        "date_iso": date_m.group(1).strip() if date_m else None,
    }


def upsert(cursor, row):
    cursor.execute(
        """
        INSERT INTO infringement_procedures (
            inf_reference, member_state, procedure_stage, sector,
            title, summary, decision_date, source_url, pdf_url,
            related_celex, policy_areas, is_test
        ) VALUES (
            %(inf_reference)s, %(member_state)s, %(procedure_stage)s, %(sector)s,
            %(title)s, %(summary)s, %(decision_date)s, %(source_url)s, %(pdf_url)s,
            %(related_celex)s, %(policy_areas)s, FALSE
        )
        ON CONFLICT (inf_reference) DO UPDATE SET
            member_state = COALESCE(EXCLUDED.member_state, infringement_procedures.member_state),
            procedure_stage = COALESCE(EXCLUDED.procedure_stage, infringement_procedures.procedure_stage),
            title = EXCLUDED.title,
            summary = COALESCE(EXCLUDED.summary, infringement_procedures.summary),
            decision_date = COALESCE(EXCLUDED.decision_date, infringement_procedures.decision_date),
            last_updated = NOW()
        """,
        row,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", default="26", help="2-digit year (e.g. 26 for 2026)")
    ap.add_argument("--from", dest="from_", type=int, default=1)
    ap.add_argument("--to", type=int, default=1500)
    ap.add_argument("--prefix", default="IP", help="IP | INF | both")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing"); sys.exit(1)

    prefixes = ["IP", "INF"] if args.prefix == "both" else [args.prefix]
    refs = []
    for px in prefixes:
        for n in range(args.from_, args.to + 1):
            refs.append(f"{px}_{args.year}_{n}")

    print(f"[INFO] Probing {len(refs)} press-corner detail URLs ({args.workers} workers, byte threshold {SHELL_THRESHOLD})")
    candidates = []
    seen = set()
    n_real = 0
    n_infringement = 0
    n_total = 0

    def process(ref):
        nonlocal n_real, n_total
        ref, status, body = fetch_detail(ref)
        n_total += 1
        if status != 200 or len(body) < SHELL_THRESHOLD:
            return None
        n_real += 1
        parsed = parse_doc(body)
        if not parsed or not parsed["title"]:
            return None
        title = parsed["title"]
        # Filter: INF references are always infringement; IP only if title matches.
        if not ref.startswith("INF") and not is_infringement_title(title):
            return None
        decision_date = None
        if parsed["date_iso"]:
            try:
                decision_date = dt.datetime.strptime(parsed["date_iso"][:10], "%Y-%m-%d").date()
            except Exception:
                pass
        summary = parsed.get("description") or ""
        return {
            "inf_reference": ref,
            "member_state": detect_member_state(title, summary),
            "procedure_stage": detect_stage(title, summary),
            "sector": None,
            "title": title[:1000],
            "summary": summary[:5000] or None,
            "decision_date": decision_date,
            "source_url": DETAIL_URL.format(ref=ref),
            "pdf_url": None,
            "related_celex": [],
            "policy_areas": [],
        }

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process, ref): ref for ref in refs}
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                row = fut.result()
            except Exception:
                row = None
            if row and row["inf_reference"] not in seen:
                seen.add(row["inf_reference"])
                candidates.append(row)
                n_infringement += 1
            if i % 100 == 0:
                print(f"  [{i}/{len(refs)}] real={n_real}  infringement-titled={n_infringement}")

    print(f"[INFO] Probed {n_total} URLs: {n_real} real pages, {n_infringement} infringement decisions.")
    if not candidates:
        print("[WARN] No infringement candidates. Nothing inserted (honest empty).")
        sys.exit(0)
    if args.dry_run:
        print("\n[DRY-RUN] First 10 candidates:")
        for c in sorted(candidates, key=lambda x: x["decision_date"] or dt.date.min, reverse=True)[:10]:
            print(f"  {c['inf_reference']:14s}  {c['member_state'] or '??'}  {c['procedure_stage'] or '?':30s}  {c['title'][:60]}")
        return

    import psycopg2
    conn = psycopg2.connect(db_url)
    try:
        with conn:
            with conn.cursor() as cur:
                for row in candidates:
                    upsert(cur, row)
        print(f"[OK] UPSERTed {len(candidates)} infringement rows.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
