"""
European Commission College Meeting Generator.

Generates Commission college meeting events (every Wednesday)
for a configurable number of months ahead.

Source: https://commission.europa.eu/strategy-and-policy/decision-making-process-commission/decision-making-during-weekly-meetings_en

Created: February 2026
"""

import logging
from datetime import date, timedelta
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

EC_DOC_REGISTER_OJ_URL = (
    "https://ec.europa.eu/transparency/documents-register/"
    "search?query=eyJjYXRlZ29yeU9iamVjdHMiOlt7ImlkIjoiT0oiLCJsYW5ndWFnZSI6ImVuIiwi"
    "dmFsdWUiOiJPSiAtIEFnZW5kYXMgb2YgQ29tbWlzc2lvbiBtZWV0aW5ncy4iLCJ0eXBlIjoiQ0FU"
    "RUdPUlkifV0sImNhdGVnb3JpZXMiOlsiT0oiXSwidHlwZU9iamVjdHMiOltdLCJ0eXBlcyI6W10s"
    "ImRlcGFydG1lbnRPYmplY3RzIjpbXSwiZGVwYXJ0bWVudHMiOltdLCJsYW5ndWFnZSI6ImVuIiwi"
    "a2V5d29yZHNTZWFyY2hUeXBlIjoiQVRfTEVBU1RfT05FIiwidGFyZ2V0IjoiVElUTEVfQU5EX0NP"
    "TlRFTlQiLCJzb3J0QnkiOiJET0NVTUVOVF9EQVRFX0RFU0MiLCJpc1JlZ3VsYXIiOnRydWUsImtl"
    "eXdvcmRzIjoiIiwicmVmZXJlbmNlIjoiIiwicGFnZSI6MX0%3D"
)


def generate_college_meetings(months_ahead: int = 6) -> List[Dict[str, Any]]:
    """
    Generate Commission college meeting events.

    The College of Commissioners meets every Wednesday (with some
    exceptions during recess periods). This generates events for
    the specified number of months ahead.

    Returns list of event dicts ready for the sync service.
    """
    events = []
    today = date.today()
    end_date = today + timedelta(days=months_ahead * 30)

    # Known recess periods (approximate, updated yearly)
    # Summer: mid-July to end-August
    # Christmas: mid-December to early January
    recess_ranges = _get_recess_ranges(today.year, end_date.year)

    # Find next Wednesday from today (or earlier for backfill)
    start = today - timedelta(days=today.weekday())  # Go to Monday
    current = start + timedelta(days=2)  # Wednesday
    if current < today - timedelta(days=30 * 3):
        # Start from 3 months ago max
        current = (today - timedelta(days=90))
        days_until_wed = (2 - current.weekday()) % 7
        current = current + timedelta(days=days_until_wed)

    while current <= end_date:
        # Skip if in recess
        in_recess = any(
            recess_start <= current <= recess_end
            for recess_start, recess_end in recess_ranges
        )

        if not in_recess:
            ext_id = f"ec_college_{current.isoformat()}"
            events.append({
                "institution": "COMMISSION",
                "event_type": "commission_college_meeting",
                "title": "College of Commissioners \u2014 Weekly Meeting",
                "description": (
                    "Weekly meeting of the College of Commissioners. "
                    "The agenda (OJ document) and minutes (PV document) "
                    "are published in the EC Register of Commission Documents."
                ),
                "start_date": current,
                "all_day": True,
                "status": "scheduled",
                "source": "ec_college",
                "external_id": ext_id,
                "source_url": EC_DOC_REGISTER_OJ_URL,
            })

        current += timedelta(weeks=1)

    logger.info(f"[OK] Generated {len(events)} Commission college meeting events")
    return events


def _get_recess_ranges(start_year: int, end_year: int) -> List[tuple]:
    """Get approximate recess date ranges for the Commission."""
    ranges = []
    for year in range(start_year, end_year + 1):
        # Summer recess: mid-July to late August
        ranges.append((
            date(year, 7, 15),
            date(year, 8, 31),
        ))
        # Christmas recess: ~20 Dec to ~5 Jan
        ranges.append((
            date(year, 12, 20),
            date(year + 1, 1, 5) if year < 9999 else date(year, 12, 31),
        ))
    return ranges
