"""
Ingest Commission expert-group meetings from RegDel into eu_calendar_events.

Source (per-month export):
  https://webgate.ec.europa.eu/regdel/web/meetings/excel/?mode=Month&month={M}&year={YYYY}&lang=en

Each row carries: Title, Start date, End date, Place, Expert group,
Policy area, Delegated act codes.

We map these to eu_calendar_events with:
  institution = 'COMMISSION'
  event_type  = 'EXPERT_GROUP_MEETING'
  title       = Title
  description = Expert group  (the formal expert-group name)
  start_date  = Start date
  end_date    = End date
  policy_areas = [Policy area]
  source_url  = RegDel deep link to the meeting (built from Delegated act code
                when present; falls back to the meetings page).

Run:
    python3.12 backend/scripts/ingest_regdel_meetings.py --month 4 --year 2026
    python3.12 backend/scripts/ingest_regdel_meetings.py --apply --month 4 --year 2026
    python3.12 backend/scripts/ingest_regdel_meetings.py --apply --year 2026   # all months
"""

from __future__ import annotations

import argparse
import io
import sys
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruIngest/1.0) Chrome/151.0.0.0"


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def fetch_month(month: int, year: int) -> bytes:
    url = (
        "https://webgate.ec.europa.eu/regdel/web/meetings/excel/"
        f"?mode=Month&month={month}&year={year}&lang=en"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def normalise_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    title = row.get("Title")
    start = row.get("Start date")
    if not isinstance(title, str) or not title.strip() or pd.isna(start):
        return None
    expert_group = row.get("Expert group") if isinstance(row.get("Expert group"), str) else None
    place = row.get("Place") if isinstance(row.get("Place"), str) else None
    policy = row.get("Policy area") if isinstance(row.get("Policy area"), str) else None
    end = row.get("End date")
    end = end if not pd.isna(end) else start

    # Delegated act codes can be a comma-separated list of CCodes — store the first
    da_codes = row.get("Delegated act codes")
    da_first = None
    if isinstance(da_codes, str) and da_codes.strip():
        da_first = da_codes.split(",")[0].strip()

    if da_first:
        source_url = (
            f"https://webgate.ec.europa.eu/regdel/#/delegatedActs?lang=en&search={da_first}"
        )
    else:
        source_url = "https://webgate.ec.europa.eu/regdel/#/meetings?lang=en"

    return {
        "id": str(uuid.uuid4()),
        "title": title.strip()[:500],
        "description": expert_group.strip()[:1000] if expert_group else None,
        "venue": place.strip()[:200] if place else None,
        "start_date": start,
        "end_date": end,
        "institution": "COMMISSION",
        "event_type": "expert_group_meeting",
        "policy_areas": [policy.strip()] if policy else [],
        "source_url": source_url,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--month", type=int, default=None,
                    help="Single month (1-12). Omit to fetch all 12.")
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    months: Iterable[int] = [args.month] if args.month else range(1, 13)

    all_rows: List[Dict[str, Any]] = []
    for m in months:
        print(f"[INFO] fetching month={m} year={args.year}...")
        try:
            bytes_ = fetch_month(m, args.year)
        except Exception as exc:
            print(f"  [ERR] fetch failed: {exc}")
            continue
        try:
            df = pd.read_excel(io.BytesIO(bytes_), engine="xlrd")
        except Exception:
            df = pd.DataFrame()
        print(f"  {len(df)} rows in Excel")
        for _, row in df.iterrows():
            rec = normalise_row(row.to_dict())
            if rec:
                all_rows.append(rec)

    print(f"[INFO] {len(all_rows)} normalised (apply={args.apply})")
    if not args.apply:
        for r in all_rows[:5]:
            print(f"  {r['start_date']:%Y-%m-%d}  {r['title'][:80]}  policy={r['policy_areas']}")
        return

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    inserted = 0
    for r in all_rows:
        try:
            cur.execute(
                """
                INSERT INTO eu_calendar_events
                  (id, title, description, venue, start_date, end_date,
                   institution, event_type, policy_areas, source_url, source,
                   first_seen, last_updated)
                VALUES
                  (%(id)s, %(title)s, %(description)s, %(venue)s,
                   %(start_date)s, %(end_date)s, %(institution)s, %(event_type)s,
                   %(policy_areas)s, %(source_url)s, 'regdel', NOW(), NOW())
                ON CONFLICT DO NOTHING
                """,
                r,
            )
            inserted += 1
        except Exception as exc:
            print(f"  [ERR] {r['title'][:50]}: {exc}")
            conn.rollback()
    conn.commit()
    conn.close()
    print(f"[DONE] inserted {inserted}")


if __name__ == "__main__":
    main()
