#!/usr/bin/env python3.12
"""
Rebuild data/canon/brubru_binding_laws.csv from eu_laws via the Brubru v2 API.

WHY
The register was scanned once from LEG_2025-11 and has been hand-patched
since. Corpus gaps (pre-2004 near-empty; base act missing from multi-act
OJ issues) and CELEX collisions leaked into the CSV silently. A proper
builder pulls the current authoritative eu_laws contents, merges the
hand-maintained columns, and produces a clean register.

DATA SOURCE
GET /api/v2/legislative/eur-lex/laws  (paged, limit=100)  -> 17,121 rows.
Requires BRUBRU_API_KEY in .env.

DUPLICATE CELEX RESOLUTION
eu_laws has ~103 CELEX groups with >1 row (122 surplus rows). Rule: pick
the row whose doc_type starts with the letter that matches the CELEX
letter (R=regulation, L=directive, D=decision). If none match, warn and
pick the row with the earliest adopted_on.

COLUMN MERGE POLICY (CSV wins for canon/Catalan; eu_laws wins for
bibliographic metadata)
- CSV wins: canon_completed, canon_completed_at, eucanon_url, legal_family,
  catalan_translated, ca_engine, ca_url, ca_html_size, ca_articles,
  ca_recitals, ca_translated_at, ca_category, ca_category_en, title_ca,
  xml_path (API does not know Formex file paths), subject_matter (not in
  API).
- eu_laws wins: title_en, doc_type, publication_date, oj_reference,
  policy_area, legal_basis (serialised), eurlex_url.
- Regenerated: celex_form, celex_year, celex_number, doc_type_normalized.
- New rows (CELEX in API but not in CSV): all API metadata, empty CSV-wins
  columns.
- CSV-only rows (CELEX in CSV but not in API): kept as-is with a
  [CSV_ONLY] tag in the diff report so you can inspect them.

OUTPUT
Default: writes data/canon/brubru_binding_laws.rebuilt.csv (side-by-side).
        Prints a diff report: inserted / updated / collision-resolved /
        csv-only counts, plus one example per category.
--apply: overwrites the live CSV after backing up to
        brubru_binding_laws.csv.bak.before_rebuild_<timestamp>.

USAGE
    python3.12 backend/scripts/rebuild_canon_register.py             # dry-run
    python3.12 backend/scripts/rebuild_canon_register.py --apply     # overwrite

ENV
    Optional: BRUBRU_API_BASE (default: https://brubru-production.up.railway.app)
    Required: BRUBRU_API_KEY (in .env)
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("[FATAL] requests not installed. pip install requests", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "data" / "canon" / "brubru_binding_laws.csv"
REBUILT_PATH = CSV_PATH.with_suffix(".rebuilt.csv")
CSV_ONLY_LIST = CSV_PATH.with_suffix(".csv_only.txt")
API_CACHE = CSV_PATH.with_suffix(".api_snapshot.json")

# CSV columns whose values are hand-maintained and must survive a rebuild.
CSV_WINS = {
    "canon_completed", "canon_completed_at", "eucanon_url", "legal_family",
    "catalan_translated", "ca_engine", "ca_url", "ca_html_size", "ca_articles",
    "ca_recitals", "ca_translated_at", "ca_category", "ca_category_en",
    "title_ca", "xml_path", "subject_matter",
}

CELEX_LETTER_TO_DOC_KIND = {
    "R": "regulation",
    "L": "directive",
    "D": "decision",
    "H": "recommendation",
    "X": None,  # varies
}


def _load_env() -> dict:
    env: dict[str, str] = {}
    envfile = ROOT / ".env"
    if not envfile.exists():
        return env
    for line in envfile.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _api_base(env: dict) -> str:
    return env.get("BRUBRU_API_BASE") or os.environ.get("BRUBRU_API_BASE") or "https://brubru-production.up.railway.app"


def _api_key(env: dict) -> str:
    key = env.get("BRUBRU_API_KEY") or os.environ.get("BRUBRU_API_KEY")
    if not key:
        raise SystemExit("[FATAL] BRUBRU_API_KEY missing (checked .env and environment).")
    return key


def fetch_all_laws(base: str, key: str) -> list[dict]:
    """Page through /laws until has_more is false. Returns raw items.

    Free-tier API is 60 req/min — pace at 1.1s between requests with a
    429-triggered 60s cooldown as safety net.
    """
    sess = requests.Session()
    sess.headers.update({"X-API-Key": key, "Accept": "application/json"})
    url = f"{base}/api/v2/legislative/eur-lex/laws"
    items: list[dict] = []
    page = 1
    LIMIT = 100
    PACE = 1.1  # seconds between requests -> ~54 req/min, safely under 60
    started = time.time()
    while True:
        loop_start = time.time()
        r = sess.get(url, params={"limit": LIMIT, "page": page}, timeout=60)
        if r.status_code == 429:
            print(f"  [rate-limit] page {page}: 60s cooldown ...")
            time.sleep(60)
            continue  # retry the same page
        if r.status_code != 200:
            raise SystemExit(f"[FATAL] {url} page={page} -> HTTP {r.status_code}: {r.text[:200]}")
        payload = r.json()
        data = payload.get("data") or []
        items.extend(data)
        total = payload.get("total")
        if page == 1 or page % 20 == 0 or not payload.get("has_more"):
            elapsed = time.time() - started
            print(f"  page {page:4d}  +{len(data):3d}  total_so_far={len(items)}/{total}  elapsed={elapsed:.1f}s")
        if not payload.get("has_more"):
            break
        page += 1
        slept = max(0.0, PACE - (time.time() - loop_start))
        if slept > 0:
            time.sleep(slept)
    return items


def resolve_duplicates(items: list[dict]) -> tuple[dict[str, dict], int]:
    """Group by CELEX; pick canonical row per group using doc_type/CELEX letter."""
    groups: dict[str, list[dict]] = {}
    for it in items:
        c = (it.get("celex") or "").strip().upper()
        if not c:
            continue
        groups.setdefault(c, []).append(it)

    winners: dict[str, dict] = {}
    resolved = 0
    for celex, rows in groups.items():
        if len(rows) == 1:
            winners[celex] = rows[0]
            continue
        # duplicate group
        resolved += 1
        letter = celex[5] if len(celex) > 5 else ""
        expected_kind = CELEX_LETTER_TO_DOC_KIND.get(letter)
        picked = None
        if expected_kind:
            for r in rows:
                dt = (r.get("doc_type") or "").lower()
                if expected_kind in dt:
                    picked = r
                    break
        if picked is None:
            # earliest adopted_on wins as tie-breaker
            def _key(r):
                d = r.get("adopted_on") or "9999-99-99"
                return d
            picked = sorted(rows, key=_key)[0]
        winners[celex] = picked
    return winners, resolved


def load_current_csv() -> tuple[list[str], dict[str, dict]]:
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    by_celex: dict[str, dict] = {}
    for r in rows:
        c = (r.get("celex") or "").strip().upper()
        if c and c not in by_celex:
            by_celex[c] = r
    return header, by_celex


def build_row_from_api(api_row: dict, csv_row: dict | None, header: list[str]) -> dict:
    """Merge one API row into a full CSV row, honouring the merge policy."""
    out = {k: "" for k in header}
    celex = (api_row.get("celex") or "").strip().upper()

    # Regenerated columns
    if "celex" in out:
        out["celex"] = celex
    if "celex_form" in out and len(celex) > 5:
        out["celex_form"] = celex[5]
    if "celex_year" in out and len(celex) >= 5:
        out["celex_year"] = celex[1:5]
    if "celex_number" in out and len(celex) > 6:
        out["celex_number"] = celex[6:]

    # eu_laws wins (bibliographic)
    if "title_en" in out:
        out["title_en"] = api_row.get("title") or ""
    if "doc_type" in out:
        out["doc_type"] = api_row.get("doc_type") or ""
    if "doc_type_normalized" in out:
        dt = (api_row.get("doc_type") or "").lower()
        for k in ("regulation", "directive", "decision", "recommendation", "opinion"):
            if k in dt:
                out["doc_type_normalized"] = k
                break
    if "publication_date" in out:
        out["publication_date"] = api_row.get("adopted_on") or ""
    if "oj_reference" in out:
        out["oj_reference"] = api_row.get("oj_reference") or ""
    if "policy_area" in out:
        out["policy_area"] = api_row.get("policy_area") or ""
    if "legal_basis" in out:
        lb = api_row.get("legal_basis") or []
        out["legal_basis"] = ", ".join(lb) if isinstance(lb, list) else str(lb or "")
    if "eurlex_url" in out:
        out["eurlex_url"] = api_row.get("eurlex_url") or (
            f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}" if celex else ""
        )

    # CSV wins (canon + Catalan + xml_path + subject_matter): overwrite any
    # eu_laws value with the CSV value where non-empty.
    if csv_row:
        for col in CSV_WINS:
            if col in out and (csv_row.get(col) or "").strip():
                out[col] = csv_row[col]

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Rebuild the canon register CSV from eu_laws via v2 API.")
    ap.add_argument("--apply", action="store_true", help="Overwrite the live CSV (with backup). Default: dry-run to *.rebuilt.csv.")
    args = ap.parse_args()

    env = _load_env()
    base = _api_base(env)
    key = _api_key(env)

    print(f"[env] api base : {base}")
    print(f"[env] csv path : {CSV_PATH}")
    print()

    # 1. Fetch (with disk cache — 230s fetch takes long, avoid on iteration)
    import json as _json
    if API_CACHE.exists():
        print(f"[cache] loading {API_CACHE.relative_to(ROOT)} (delete to re-fetch)")
        api_items = _json.loads(API_CACHE.read_text())
    else:
        print("[fetch] paging /api/v2/legislative/eur-lex/laws ...")
        api_items = fetch_all_laws(base, key)
        API_CACHE.write_text(_json.dumps(api_items))
        print(f"[cache] wrote {API_CACHE.relative_to(ROOT)}")
    print(f"[fetch] have {len(api_items)} API rows")

    # 2. Resolve duplicates
    winners, resolved = resolve_duplicates(api_items)
    print(f"[dedup] {resolved} CELEX groups had duplicates; kept the row matching CELEX letter.")
    print(f"[dedup] {len(winners)} unique CELEXes.")

    # 3. Load current CSV
    header, csv_by_celex = load_current_csv()
    print(f"[csv]   header: {len(header)} cols; existing rows: {len(csv_by_celex)}")

    # 4. Merge
    api_celexes = set(winners.keys())
    csv_celexes = set(csv_by_celex.keys())
    inserted = updated = 0
    example_insert = example_update = None
    out_rows: list[dict] = []
    for celex in sorted(api_celexes):
        csv_row = csv_by_celex.get(celex)
        new_row = build_row_from_api(winners[celex], csv_row, header)
        if csv_row is None:
            inserted += 1
            if example_insert is None:
                example_insert = celex
        else:
            updated += 1
            if example_update is None:
                example_update = celex
        out_rows.append(new_row)

    # 5. CSV-only rows (keep with tag) + write list for follow-up
    csv_only = sorted(csv_celexes - api_celexes)
    for celex in csv_only:
        out_rows.append(csv_by_celex[celex])
    if csv_only:
        lines = ["# CELEXes in the CSV register but MISSING from eu_laws (via /api/v2/legislative/eur-lex/laws).",
                 f"# Generated: {datetime.now().isoformat()}",
                 f"# Count: {len(csv_only)}",
                 ""]
        for c in csv_only:
            row = csv_by_celex[c]
            lines.append(f"{c}\t{row.get('doc_type','')[:40]}\t{(row.get('title_en') or '')[:120]}")
        CSV_ONLY_LIST.write_text("\n".join(lines) + "\n")
        print(f"[csv-only] wrote {CSV_ONLY_LIST.relative_to(ROOT)}")

    # 6. Write output
    target = CSV_PATH if args.apply else REBUILT_PATH
    if args.apply:
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        backup = CSV_PATH.with_suffix(f".csv.bak.before_rebuild_{ts}")
        shutil.copy2(CSV_PATH, backup)
        print(f"[backup] {backup.relative_to(ROOT)}")

    with target.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(out_rows)

    # 7. Report
    print()
    print("=== rebuild report ===")
    print(f"  API rows fetched         : {len(api_items)}")
    print(f"  unique CELEX groups      : {len(winners)}")
    print(f"  duplicates resolved      : {resolved}")
    print(f"  existing CSV rows        : {len(csv_by_celex)}")
    print(f"  merged (updated) rows    : {updated}")
    print(f"  inserted (new) rows      : {inserted}")
    print(f"  CSV-only rows kept       : {len(csv_only)}")
    print(f"  total output rows        : {len(out_rows)}")
    print(f"  wrote                    : {target.relative_to(ROOT)}")
    print()
    if example_insert:
        print(f"  example new CELEX     : {example_insert}")
    if example_update:
        print(f"  example merged CELEX  : {example_update}")
    if csv_only:
        print(f"  first 5 CSV-only CELEX: {csv_only[:5]}")
    print()
    if not args.apply:
        print("[dry-run] no changes to live CSV. Re-run with --apply to overwrite.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
