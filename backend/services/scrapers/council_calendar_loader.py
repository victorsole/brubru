"""
Council and ECB Calendar Loader.

Reads Council/European Council/ECB calendar data from static JSON files
and converts them into EUCalendarEvent-compatible dicts for the sync service.

Source: knowledge_base/calendars/council_meetings_{year}.json
ECB dates from ecb.europa.eu/press/calendars/mgcgc

Created: February 2026
"""

import json
import os
import logging
from datetime import datetime, date
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def load_council_meetings(year: int) -> List[Dict[str, Any]]:
    """
    Load Council of the EU and European Council meetings from JSON.

    Returns list of dicts ready for the sync service.
    """
    calendar_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "knowledge_base", "calendars",
    )
    filepath = os.path.join(calendar_dir, f"council_meetings_{year}.json")

    if not os.path.exists(filepath):
        logger.warning(f"[WARN] Council meetings file not found: {filepath}")
        return []

    with open(filepath, "r") as f:
        data = json.load(f)

    events = []
    seen_external_ids = set()

    for meeting in data.get("meetings", []):
        title = meeting.get("title", "")
        institution = meeting.get("institution", "COUNCIL")
        event_type = meeting.get("event_type", "council_meeting")
        configuration = meeting.get("configuration")
        source_url = meeting.get("url", "https://www.consilium.europa.eu/en/meetings/calendar/")

        # Handle single-day and multi-day meetings
        start_str = meeting.get("date") or meeting.get("date_start")
        end_str = meeting.get("date_end")

        if not start_str or not title:
            continue

        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date() if end_str else None

        # Build external ID
        clean_title = title.lower().replace(" ", "_")[:40]
        ext_id = f"council_{start_str}_{clean_title}"

        if ext_id in seen_external_ids:
            continue
        seen_external_ids.add(ext_id)

        event = {
            "institution": institution,
            "event_type": event_type,
            "title": title,
            "start_date": start_date,
            "end_date": end_date,
            "all_day": True,
            "status": "confirmed",
            "council_configuration": configuration,
            "source": "council_calendar_json",
            "external_id": ext_id,
            "source_url": source_url,
        }
        events.append(event)

    logger.info(f"[OK] Loaded {len(events)} Council/European Council meetings for {year}")
    return events


def load_ecb_meetings(year: int) -> List[Dict[str, Any]]:
    """
    Load ECB Governing Council meeting dates from the same JSON file.

    Returns list of dicts ready for the sync service.
    """
    calendar_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "knowledge_base", "calendars",
    )
    filepath = os.path.join(calendar_dir, f"council_meetings_{year}.json")

    if not os.path.exists(filepath):
        logger.warning(f"[WARN] Council meetings file not found: {filepath}")
        return []

    with open(filepath, "r") as f:
        data = json.load(f)

    ecb_data = data.get(f"ecb_governing_council_{year}", {})
    ecb_meetings = ecb_data.get("meetings", [])

    events = []
    for meeting in ecb_meetings:
        start_str = meeting.get("date_start")
        end_str = meeting.get("date_end")
        meeting_type = meeting.get("type", "monetary_policy")

        if not start_str:
            continue

        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date() if end_str else None

        title = "ECB Governing Council \u2014 Monetary Policy Meeting"
        if meeting_type != "monetary_policy":
            title = "ECB Governing Council \u2014 Non-Monetary Policy Meeting"

        ext_id = f"ecb_gc_{start_str}"

        events.append({
            "institution": "ECB",
            "event_type": "ecb_governing_council",
            "title": title,
            "description": (
                "The Governing Council of the European Central Bank meets to assess "
                "economic and monetary developments and take monetary policy decisions. "
                "Interest rate decisions are announced on the second day."
            ),
            "start_date": start_date,
            "end_date": end_date,
            "all_day": True,
            "status": "confirmed",
            "source": "ecb_calendar_json",
            "external_id": ext_id,
            "source_url": "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html",
        })

    logger.info(f"[OK] Loaded {len(events)} ECB Governing Council meetings for {year}")
    return events
