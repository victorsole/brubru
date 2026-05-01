"""
Ingest Commission infringement procedure decisions from press-corner.

NO CURATED SEED. Every row comes from a real press-corner search result with
a row-specific source_url like
https://ec.europa.eu/commission/presscorner/detail/en/INF_25_4001

Strategy:
  1. Hit the public press-corner search API filtered to keyword "infringement"
     and document type "Press release" + "Speech" if needed.
  2. For each result, parse the INF/yy/nnnn reference, member state,
     procedure stage, sector. Store the press-corner URL as source_url.
  3. UPSERT on inf_reference. Skip rows where reference can't be derived.

Run: python3.12 backend/scripts/ingest_infringements.py [--limit N] [--dry-run]
"""

import argparse
import datetime as dt
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

import json

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


def get_env(k):
    env = ROOT / ".env"
    if not env.exists():
        return ""
    for line in env.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


SEARCH_URL = "https://ec.europa.eu/commission/presscorner/api/search"
DETAIL_URL = "https://ec.europa.eu/commission/presscorner/detail/en/{ref}"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruInfringementCrawler/1.0; +https://brubru.beresol.eu)"

# Map stage keywords → canonical procedure stage
STAGE_KEYWORDS = [
    ("letter of formal notice", "letter_of_formal_notice"),
    ("reasoned opinion", "reasoned_opinion"),
    ("referral to the court", "referral_to_court"),
    ("refer to the court", "referral_to_court"),
    ("court of justice", "referral_to_court"),
    ("closure", "closure"),
    ("closed", "closure"),
    ("additional reasoned opinion", "additional_reasoned_opinion"),
    ("additional letter", "additional_letter_of_formal_notice"),
]

# ISO-3166 alpha-2 codes recognised in Commission communications.
MEMBER_STATES = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "EL",
    "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE", "GR",  # GR is sometimes used instead of EL
}
COUNTRY_NAMES = {
    "Austria": "AT", "Belgium": "BE", "Bulgaria": "BG", "Croatia": "HR",
    "Cyprus": "CY", "Czechia": "CZ", "Denmark": "DK", "Estonia": "EE",
    "Finland": "FI", "France": "FR", "Germany": "DE", "Greece": "EL",
    "Hungary": "HU", "Ireland": "IE", "Italy": "IT", "Latvia": "LV",
    "Lithuania": "LT", "Luxembourg": "LU", "Malta": "MT", "Netherlands": "NL",
    "Poland": "PL", "Portugal": "PT", "Romania": "RO", "Slovakia": "SK",
    "Slovenia": "SI", "Spain": "ES", "Sweden": "SE",
}


def http_get(url, params=None, timeout=30):
    if params:
        from urllib.parse import urlencode
        url = url + ("&" if "?" in url else "?") + urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/html,*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()


def parse_inf_reference(text):
    """Extract INF/yy/nnnn or IP/yy/nnnn references."""
    m = re.search(r"\b(INF[_/](?:\d{2}|\d{4})[_/]\d{3,5})\b", text or "", re.IGNORECASE)
    if m:
        return m.group(1).upper().replace("/", "_")
    return None


def detect_stage(title, summary):
    """Pick the procedure stage from title + summary keywords."""
    blob = f"{title or ''} {summary or ''}".lower()
    for keyword, stage in STAGE_KEYWORDS:
        if keyword in blob:
            return stage
    return None


def detect_member_state(title, summary):
    blob = f"{title or ''} {summary or ''}"
    # Try country names first (more specific)
    for name, code in COUNTRY_NAMES.items():
        if re.search(rf"\b{re.escape(name)}\b", blob):
            return code
    # Then iso-2
    m = re.search(r"\b([A-Z]{2})\b", title or "")
    if m and m.group(1) in MEMBER_STATES:
        return m.group(1)
    return None


def fetch_search_page(keyword="infringement", page=0, page_size=20):
    """Press-corner search API. Returns parsed JSON or empty dict.

    Real endpoint: https://ec.europa.eu/commission/presscorner/api/search
    Response shape:
      {
        "totalNumber": ...,
        "pageNumber": 0,
        "docuLanguageListResources": [
          {"docuky": 123, "title": "...", "leadText": "...",
           "eventDate": "2026-04-30", "languageCode": "EN", "reference": "INF/26/4101"}
        ]
      }
    """
    params = {
        "keywords": keyword,
        "language": "en",
        "size": page_size,
        "pageNumber": page,
        "sort": "date_desc",
    }
    status, body = http_get(SEARCH_URL, params=params)
    if status != 200:
        return {}, status
    try:
        return json.loads(body), status
    except Exception:
        return {}, status


def upsert_row(cursor, row):
    """UPSERT into infringement_procedures on inf_reference."""
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
            member_state = EXCLUDED.member_state,
            procedure_stage = EXCLUDED.procedure_stage,
            sector = COALESCE(EXCLUDED.sector, infringement_procedures.sector),
            title = EXCLUDED.title,
            summary = COALESCE(EXCLUDED.summary, infringement_procedures.summary),
            decision_date = EXCLUDED.decision_date,
            source_url = EXCLUDED.source_url,
            pdf_url = COALESCE(EXCLUDED.pdf_url, infringement_procedures.pdf_url),
            last_updated = NOW()
        """,
        row,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20, help="Max records to ingest this run")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing"); sys.exit(1)

    print(f"[INFO] Searching presscorner for 'infringement' (limit={args.limit})")

    # Live presscorner JSON API at /api/search with response field
    # docuLanguageListResources containing {docuky, title, leadText, eventDate, reference}.
    candidates = []
    page = 0
    seen_refs = set()
    while len(candidates) < args.limit and page < 20:
        data, code = fetch_search_page(page=page, page_size=20)
        items = data.get("docuLanguageListResources") or []
        if not items:
            print(f"  [WARN] page {page}: code={code}, no items in response. Stopping.")
            break
        for it in items:
            title = (it.get("title") or "").strip()
            summary = (it.get("leadText") or "").strip()
            # The press-corner search JSON exposes the reference under refCode
            # (e.g. "INF/26/720"), not "reference".
            ref_field = it.get("refCode") or ""
            inf_ref = parse_inf_reference(ref_field) or parse_inf_reference(title)
            if not inf_ref or inf_ref in seen_refs:
                continue
            # Filter to actual INF references only — IP/yy/nnnn (general press)
            # is broader than infringement procedures.
            if not inf_ref.startswith("INF"):
                continue
            seen_refs.add(inf_ref)
            decision_date = None
            try:
                d = it.get("eventDate")
                if d:
                    decision_date = dt.datetime.strptime(d[:10], "%Y-%m-%d").date()
            except Exception:
                pass
            candidates.append({
                "inf_reference": inf_ref,
                "member_state": detect_member_state(title, summary),
                "procedure_stage": detect_stage(title, summary),
                "sector": None,
                "title": title[:1000] or f"Infringement decision {inf_ref}",
                "summary": summary[:5000] or None,
                "decision_date": decision_date,
                "source_url": DETAIL_URL.format(ref=inf_ref),
                "pdf_url": None,
                "related_celex": [],
                "policy_areas": [],
            })
            if len(candidates) >= args.limit:
                break
        page += 1
        time.sleep(1.1)

    print(f"[INFO] Built {len(candidates)} candidate rows from real source.")
    if not candidates:
        print("[WARN] No candidates produced — press-corner returned no parseable INF refs.")
        print("       This is honest empty: do not insert synthetic rows.")
        sys.exit(0)

    if args.dry_run:
        print("\n[DRY-RUN] First 3 candidates:")
        for c in candidates[:3]:
            print(f"  {c['inf_reference']:18s}  {c['member_state'] or '??':2s}  {c['procedure_stage'] or '?':30s}  {c['title'][:60]}")
            print(f"     -> {c['source_url']}")
        return

    import psycopg2
    conn = psycopg2.connect(db_url)
    inserted = 0
    try:
        with conn:
            with conn.cursor() as cur:
                for row in candidates:
                    upsert_row(cur, row)
                    inserted += 1
        print(f"[OK] UPSERTed {inserted} rows into infringement_procedures.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
