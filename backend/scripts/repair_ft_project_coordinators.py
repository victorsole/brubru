"""
Repair `ft_funded_projects.coordinator_name` on the rows that hold truncated JSON.

`ingest_ft_projects_nonh2020.py` used to store the coordinator with
`str(participants[0])[:300]`, which put SEDIA's raw participants JSON into a
column called coordinator_name and cut it 300 characters in, mid-string. All
28,125 affected rows are EXACTLY 300 characters long and not one is parseable.

The ingester is fixed, but a corrected value only lands when a re-ingest next
touches that project_id, and the rows are visibly broken now: the Tenderator
feed runs `_clean_coordinator` over them, cannot parse the fragment, and renders
an empty Organisation rather than a name.

What survives the cut is the head of the first participant, which carries
legalName and pic. This reads those back out and writes the name into the column
that was always supposed to hold it, plus the country when it survived too
(coordinator_country is null on every one of these rows, because that ingester
never wrote the column at all).

Rows whose fragment yields no legal name are LEFT ALONE rather than blanked: a
wrong-looking value the operator can still see beats a null that hides the
problem.

Run:
    python3.12 backend/scripts/repair_ft_project_coordinators.py            # dry run
    python3.12 backend/scripts/repair_ft_project_coordinators.py --apply
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.tenders.country_codes import normalise_country  # noqa: E402

_LEGAL_NAME = re.compile(r'"legalName"\s*:\s*"((?:[^"\\]|\\.)*)"')
_COUNTRY_ABBR = re.compile(r'"abbreviation"\s*:\s*"([A-Za-z]{2,3})"')


def _unescape(value: str) -> str:
    """Decode JSON escapes in a regex-captured fragment (\\u0027 -> ')."""
    try:
        return json.loads(f'"{value}"')
    except (ValueError, TypeError):
        return value


def recover(raw: str) -> Tuple[Optional[str], Optional[str]]:
    """(legal name, country) recoverable from a truncated participants blob."""
    name_match = _LEGAL_NAME.search(raw)
    if not name_match:
        return None, None
    country_match = _COUNTRY_ABBR.search(raw)
    return (
        _unescape(name_match.group(1)).strip()[:500] or None,
        normalise_country(country_match.group(1)) if country_match else None,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the repaired values")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    db = SessionLocal()
    repaired = country_filled = unrecoverable = 0
    try:
        sql = (
            "SELECT id, coordinator_name FROM ft_funded_projects "
            "WHERE coordinator_name LIKE '[{%' OR coordinator_name LIKE '{%'"
        )
        if args.limit:
            sql += f" LIMIT {int(args.limit)}"
        rows = db.execute(text(sql)).fetchall()
        print(f"[source] {len(rows)} rows holding a JSON fragment")

        for row in rows:
            name, country = recover(row.coordinator_name)
            if not name:
                unrecoverable += 1
                continue
            repaired += 1
            if country:
                country_filled += 1
            if repaired <= 5:
                print(f"  {name[:58]:60} {country or '--'}")
            if args.apply:
                db.execute(
                    text(
                        "UPDATE ft_funded_projects "
                        "SET coordinator_name = :name, "
                        "    coordinator_country = COALESCE(coordinator_country, :country), "
                        "    last_updated = now() "
                        "WHERE id = :id"
                    ),
                    {"name": name, "country": country, "id": row.id},
                )

        if args.apply:
            db.commit()

        print(
            f"\n[repair] recovered={repaired} country_filled={country_filled} "
            f"left_alone={unrecoverable} applied={args.apply}"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
