"""
EP Calendar Loader.

Reads EP parliamentary calendar JSON files and converts them
into EUCalendarEvent-compatible dicts for the sync service.

Source: knowledge_base/calendars/ep_calendar_{year}.json

Created: February 2026
"""

import json
import os
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Day name to weekday offset (Monday=0)
DAY_OFFSETS = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}

# Activity type to event_type mapping.
#
# external_activities used to be mapped onto group_week because the DB enum
# had no value for it. That told users the political groups were meeting in
# Brussels during what is actually a constituency week. Migration 203 added
# the enum value; the mapping is now 1:1 and must stay that way.
ACTIVITY_TYPE_MAP = {
    "plenary_session": "plenary_session",
    "committee_week": "committee_week",
    "group_week": "group_week",
    "recess": "recess",
    "external_activities": "external_activities",
}

# Activity type to human-readable title.
#
# These titles are user-facing: they are read aloud in chat answers and are
# interpolated into proactive briefings. Each must be unambiguous on its own,
# because a reader only ever sees the title, never the activity_type key.
ACTIVITY_TITLES = {
    "plenary_session": "EP Plenary Session",
    "committee_week": "EP Committee Week",
    "group_week": "EP Political Group Week",
    "recess": "EP Recess",
    "external_activities": "EP Constituency Week (external parliamentary activities)",
}

# Activity type to description
ACTIVITY_DESCRIPTIONS = {
    "plenary_session": (
        "Plenary session of the European Parliament in Strasbourg. "
        "MEPs debate and vote on legislative proposals and resolutions."
    ),
    "committee_week": (
        "EP Committee Week: standing committees hold their regular meetings "
        "(AGRI, BUDG, ECON, EMPL, ENVI, IMCO, ITRE, JURI, LIBE, TRAN, etc.). "
        "Draft agendas and meeting documents are published on the EP committees "
        "latest documents page."
    ),
    "group_week": (
        "Political group week: EP political groups (EPP, S&D, Renew, "
        "Greens/EFA, ECR, The Left, PfE) hold internal meetings "
        "to prepare positions and coordinate strategy."
    ),
    "recess": None,
    "external_activities": (
        "EP constituency week (external parliamentary activities): neither the "
        "plenary nor the standing committees sit. MEPs work in their home "
        "countries and constituencies; delegations, fact-finding missions and "
        "inter-parliamentary meetings may take place. There is no committee "
        "agenda and no plenary agenda for this week."
    ),
}

# Source URL per activity type
ACTIVITY_SOURCE_URLS = {
    "plenary_session": "https://www.europarl.europa.eu/plenary/en/agendas.html",
    "committee_week": "https://www.europarl.europa.eu/committees/en/documents/latest-documents",
    "group_week": "https://www.europarl.europa.eu/politicalgroups/en",
    "recess": "https://www.europarl.europa.eu/plenary/en/agendas.html",
    "external_activities": "https://www.europarl.europa.eu/plenary/en/agendas.html",
}


def _parse_date_range(dates_str: str) -> tuple:
    """Parse 'YYYY-MM-DD to YYYY-MM-DD' into (start_date, end_date)."""
    parts = dates_str.split(" to ")
    start = datetime.strptime(parts[0].strip(), "%Y-%m-%d").date()
    end = datetime.strptime(parts[1].strip(), "%Y-%m-%d").date()
    return start, end


def _get_weekday_date(week_start: date, day_name: str) -> Optional[date]:
    """Get date for a specific day name within the week."""
    offset = DAY_OFFSETS.get(day_name)
    if offset is None:
        return None
    # week_start is Monday
    return week_start + timedelta(days=offset)


def load_ep_calendar(year: int) -> List[Dict[str, Any]]:
    """
    Load EP calendar for a given year and expand into individual events.

    For plenary sessions with session_days, creates individual day events.
    For other activity types, creates a single multi-day event per week.

    Returns list of dicts ready for the sync service.
    """
    calendar_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "knowledge_base", "calendars",
    )
    filepath = os.path.join(calendar_dir, f"ep_calendar_{year}.json")

    if not os.path.exists(filepath):
        logger.warning(f"[WARN] EP calendar file not found: {filepath}")
        return []

    with open(filepath, "r") as f:
        data = json.load(f)

    events = []
    seen_external_ids = set()

    # Process special dates
    for key, special in data.get("special_dates", {}).items():
        ext_id = f"ep_{year}_special_{key}"
        if ext_id in seen_external_ids:
            continue
        seen_external_ids.add(ext_id)
        events.append({
            "institution": "EP",
            "event_type": "special_date",
            "title": special.get("description", key.replace("_", " ").title()),
            "start_date": datetime.strptime(special["date"], "%Y-%m-%d").date(),
            "all_day": True,
            "status": "confirmed",
            "source": "ep_calendar_json",
            "external_id": ext_id,
            "source_url": "https://www.europarl.europa.eu/plenary/en/home",
        })

    # Process months and weeks
    for month_name, month_data in data.get("months", {}).items():
        for week in month_data.get("weeks", []):
            week_num = week.get("week_number")
            activity = week.get("activity_type", "")
            dates_str = week.get("dates", "")

            if not dates_str or not activity:
                continue

            start_date, end_date = _parse_date_range(dates_str)
            event_type = ACTIVITY_TYPE_MAP.get(activity, activity)
            title = ACTIVITY_TITLES.get(activity, f"EP {activity.replace('_', ' ').title()}")

            # For plenary sessions with session_days, create per-day events
            session_days = week.get("session_days", [])
            if activity == "plenary_session" and session_days:
                for day_name in session_days:
                    day_date = _get_weekday_date(start_date, day_name)
                    if day_date is None:
                        continue

                    # Identity is the DATE, not the upstream week label
                    # (calendar audit, 3 Sep 2026). This used to be
                    # f"ep_{year}_w{week_num}_plenary_{day_name.lower()}", and
                    # `week_num` comes from the source JSON rather than from the
                    # date. When the EP relabelled the September plenary week
                    # 37 -> 38 between the 21 July and 24 August runs, every day
                    # of that session got a NEW external_id, the
                    # uq_calendar_source_external_id index saw an unseen key,
                    # and My EU Calendar showed the plenary twice. 28 rows.
                    # A date is stable; a week label upstream is not.
                    ext_id = f"ep_{year}_plenary_{day_date.isoformat()}"
                    if ext_id in seen_external_ids:
                        continue
                    seen_external_ids.add(ext_id)

                    day_index = session_days.index(day_name) + 1
                    source_url = ACTIVITY_SOURCE_URLS.get(
                        activity, "https://www.europarl.europa.eu/plenary/en/agendas.html"
                    )
                    description = ACTIVITY_DESCRIPTIONS.get(activity)
                    events.append({
                        "institution": "EP",
                        "event_type": event_type,
                        "title": f"{title} (Day {day_index})",
                        "description": description,
                        "start_date": day_date,
                        "all_day": True,
                        "status": "confirmed",
                        "ep_activity_type": activity,
                        "source": "ep_calendar_json",
                        "external_id": ext_id,
                        "source_url": source_url,
                    })
            elif week.get("daily") and set(week["daily"].values()) != {activity}:
                # Mixed week: the days are not all the same activity (e.g.
                # 7-11 Sep 2026 is committee / group / group / committee).
                # Emit one event per day so anything answering "what is on
                # TODAY" gets the right answer instead of the week label.
                for day_name, day_activity in week["daily"].items():
                    day_date = _get_weekday_date(start_date, day_name)
                    if day_date is None:
                        continue

                    ext_id = f"ep_{year}_w{week_num}_{day_name.lower()}_{day_activity}"
                    if ext_id in seen_external_ids:
                        continue
                    seen_external_ids.add(ext_id)

                    events.append({
                        "institution": "EP",
                        "event_type": ACTIVITY_TYPE_MAP.get(day_activity, day_activity),
                        "title": ACTIVITY_TITLES.get(
                            day_activity,
                            f"EP {day_activity.replace('_', ' ').title()}",
                        ),
                        "description": ACTIVITY_DESCRIPTIONS.get(day_activity),
                        "start_date": day_date,
                        "all_day": True,
                        "status": "confirmed",
                        "ep_activity_type": day_activity,
                        "source": "ep_calendar_json",
                        "external_id": ext_id,
                        "source_url": ACTIVITY_SOURCE_URLS.get(
                            day_activity,
                            "https://www.europarl.europa.eu/plenary/en/agendas.html",
                        ),
                    })
            else:
                # Single multi-day event for the week
                ext_id = f"ep_{year}_w{week_num}_{activity}"
                if ext_id in seen_external_ids:
                    continue
                seen_external_ids.add(ext_id)

                # Skip weekends for non-recess: Mon-Fri only
                actual_end = end_date
                if activity != "recess":
                    actual_end = start_date + timedelta(days=4)  # Friday
                    if actual_end > end_date:
                        actual_end = end_date

                source_url = ACTIVITY_SOURCE_URLS.get(
                    activity, "https://www.europarl.europa.eu/plenary/en/agendas.html"
                )
                description = ACTIVITY_DESCRIPTIONS.get(activity)
                events.append({
                    "institution": "EP",
                    "event_type": event_type,
                    "title": title,
                    "description": description,
                    "start_date": start_date,
                    "end_date": actual_end,
                    "all_day": True,
                    "status": "confirmed",
                    "ep_activity_type": activity,
                    "source": "ep_calendar_json",
                    "external_id": ext_id,
                    "source_url": source_url,
                })

    logger.info(f"[OK] Loaded {len(events)} EP calendar events for {year}")
    return events
