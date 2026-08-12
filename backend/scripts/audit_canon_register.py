#!/usr/bin/env python3.12
"""
Audit the canon register (data/canon/brubru_binding_laws.csv) against the
canon pages actually live under frontend/public/eucanon/*/.

WHY
Step 9 of the /canon workflow (mark the CSV row canon_completed=True) is
a manual step at the end of a long session, and it gets dropped. When it
does, the "pick the next law" selector still matches the shipped law's
row and a future /canon run could re-process a live page.

WHAT IT REPORTS
- MISSING_ROW: an eucanon/<slug>/index.html exists but no CSV row carries
  the matching eucanon_url. The law is invisible to the register.
- UNMARKED: a CSV row's eucanon_url points at a live page but the row is
  not canon_completed=True. Step 9 was skipped.
- ORPHAN: a CSV row is canon_completed=True but its eucanon_url does not
  resolve to a live page (typo, deleted, undeployed).
- COLLISION: two or more canon_completed=True rows point at the same slug.
- WRONG_ACT_HINT: a slug directory exists but no CSV row's celex matches
  the CELEX embedded in the slug — likely a wrong-act row is holding the
  CELEX (see pharma pharmacovigilance bug, 5 Aug 2026).

EXIT
Non-zero if any drift is detected. Wire into the /canon SKILL pre-flight
so a session refuses to start on a stale register.

Run:
    python3.12 backend/scripts/audit_canon_register.py
"""
from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "data" / "canon" / "brubru_binding_laws.csv"
EUCANON_DIR = ROOT / "frontend" / "public" / "eucanon"

# Regime hubs are canon pages that describe a whole regulatory regime rather than
# one binding act, so they are intentionally NOT keyed to a single CELEX row in
# the register. They are built from live Brubru API data (see
# data/canon/_build_dpp_hub.py), not from a Formex XML, and re-run to refresh.
# Excluded from the CSV-consistency checks so they do not trip MISSING_ROW.
REGIME_HUBS = {
    "digital-product-passport",  # /api/v2/dpp regime (ESPR 2024/1781 + 13 acts)
}

# Extract CELEX from a slug like "2016-679_gdpr" or "2014-536_ctr".
# The slug encodes YEAR-NUMBER; we don't know the R/L/D letter from the slug
# alone, so we look for any CELEX that matches on year+number and pick the
# first canon_completed one.
SLUG_RE = re.compile(r"^(\d{4})-(\d{1,4})_")


def _url_slug(url: str) -> str | None:
    if not url:
        return None
    m = re.search(r"/eucanon/([^/]+)/", url)
    return m.group(1) if m else None


def main() -> int:
    if not CSV_PATH.is_file():
        print(f"[ERROR] CSV not found: {CSV_PATH}", file=sys.stderr)
        return 2
    if not EUCANON_DIR.is_dir():
        print(f"[ERROR] eucanon dir not found: {EUCANON_DIR}", file=sys.stderr)
        return 2

    live_slugs = sorted(
        d.name for d in EUCANON_DIR.iterdir()
        if d.is_dir() and (d / "index.html").is_file()
        and d.name not in REGIME_HUBS
    )
    live_hubs = sorted(
        d.name for d in EUCANON_DIR.iterdir()
        if d.is_dir() and (d / "index.html").is_file()
        and d.name in REGIME_HUBS
    )

    rows_by_slug: dict[str, list[dict]] = defaultdict(list)
    all_rows: list[dict] = []
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_rows.append(row)
            slug = _url_slug(row.get("eucanon_url", "") or "")
            if slug:
                rows_by_slug[slug].append(row)

    missing_row: list[str] = []
    unmarked: list[str] = []
    collision: list[tuple[str, int]] = []
    wrong_act_hint: list[str] = []

    for slug in live_slugs:
        matches = rows_by_slug.get(slug, [])
        if not matches:
            missing_row.append(slug)
            m = SLUG_RE.match(slug)
            if m:
                year, num = m.group(1), m.group(2).zfill(4)
                have_celex = any(
                    (r.get("celex") or "").endswith(num) and (r.get("celex") or "").startswith("3" + year)
                    for r in all_rows
                )
                if have_celex:
                    wrong_act_hint.append(slug)
            continue
        complete = [r for r in matches if r.get("canon_completed") == "True"]
        if not complete:
            unmarked.append(slug)
        if len(complete) > 1:
            collision.append((slug, len(complete)))

    orphan: list[str] = []
    live_set = set(live_slugs)
    for row in all_rows:
        if row.get("canon_completed") != "True":
            continue
        slug = _url_slug(row.get("eucanon_url", "") or "")
        if slug and slug not in live_set:
            orphan.append(f"{row.get('celex', '?')} -> {slug}")

    total_live = len(live_slugs)
    total_marked = sum(1 for r in all_rows if r.get("canon_completed") == "True")

    print(f"[audit] live eucanon pages : {total_live}")
    print(f"[audit] canon_completed rows: {total_marked}")
    if live_hubs:
        print(f"[audit] regime hubs (excl.) : {len(live_hubs)} ({', '.join(live_hubs)})")
    print()

    def _section(title: str, items: list, formatter=str) -> None:
        print(f"--- {title} ({len(items)}) ---")
        for it in items:
            print(f"  {formatter(it)}")
        print()

    _section("MISSING_ROW (page live, no CSV row with matching eucanon_url)", missing_row)
    _section("UNMARKED (row exists, canon_completed != True)", unmarked)
    _section("ORPHAN (row marked True, no live page)", orphan)
    _section("COLLISION (multiple completed rows for same slug)", collision, lambda t: f"{t[0]} x{t[1]}")
    _section("WRONG_ACT_HINT (slug has no matching CELEX row but adjacent CELEX exists)", wrong_act_hint)

    drift = bool(missing_row or unmarked or orphan or collision)
    if drift:
        print("[FAIL] register drift detected. Backfill / correct rows before running /canon.")
        return 1
    print("[OK] register consistent with live eucanon pages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
