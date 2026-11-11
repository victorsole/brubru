"""What a committee meeting without a transcript can still honestly say.

Since June 2026 the European Parliament's video service does not let its recordings be
downloaded (its segments answer 403 to anything but its own player), so no committee meeting
has been transcribed since. Until 11 Nov 2026 /parliament/webstreams answered those meetings
as `PENDING` for ever, with a body of five lines of metadata, and the job that registers them
said `success` every run.

This module holds the two honest things left: the reason, in words, and the sitting's own
agenda, which Brubru already holds from Parliament's eMeeting.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# The last committee meeting transcribed was held on 8 June 2026; the recordings moved to the
# service that refuses downloads right after.
RECORDINGS_CLOSED_FROM = date(2026, 6, 9)
# A meeting of several days is one agenda, dated on its first day.
AGENDA_LOOKBACK_DAYS = 4

_EVENT_START = re.compile(r"_(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})-")
_SITTING = re.compile(
    r"^\s*(\d{1,2}) ([A-Za-z]+) (\d{4}),\s*(\d{1,2})\.(\d{2})(?:\s*-\s*(\d{1,2})\.(\d{2}))?")
_MONTHS = {m: i for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"), 1)}

NOTE_NOT_HELD = "No transcript yet: the meeting has not been held."
NOTE_CLOSED = ("No transcript: the European Parliament's video service does not allow its "
               "recordings to be downloaded, so this meeting has not been transcribed. "
               "The recording can be watched at the meeting's page.")
NOTE_NONE = "No transcript: this meeting's recording was not transcribed."


def meeting_start(event_id: Optional[str]) -> Optional[Tuple[date, int]]:
    """(day, minutes after midnight) a webstream starts, read from its event id."""
    m = _EVENT_START.search(event_id or "")
    if not m:
        return None
    y, mo, d, h, mi = (int(x) for x in m.groups())
    try:
        return date(y, mo, d), h * 60 + mi
    except ValueError:
        return None


def _sitting(title: Optional[str]) -> Optional[Tuple[date, int, Optional[int]]]:
    """(day, start, end) of an agenda's sitting marker: '10 November 2026, 09.00 - 12.45'."""
    m = _SITTING.match(title or "")
    if not m or m.group(2).lower() not in _MONTHS:
        return None
    try:
        day = date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
    except ValueError:
        return None
    start = int(m.group(4)) * 60 + int(m.group(5))
    end = int(m.group(6)) * 60 + int(m.group(7)) if m.group(6) else None
    return day, start, end


def sitting_items(items: Optional[List[Dict[str, Any]]], day: date,
                  start: Optional[int]) -> List[Dict[str, Any]]:
    """The agenda items of the sitting a webstream shows, as [{number, title, procedure_refs}].

    An agenda lists its sittings as markers, each followed by its items. The webstream's
    sitting is the one on its day that starts when it starts, or whose hours contain its
    start; a day with a single sitting is that sitting. Several sittings and no match: none,
    rather than another sitting's items.
    """
    sittings: List[Tuple[Tuple[date, int, Optional[int]], List[Dict[str, Any]]]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("type"), dict) and item["type"].get("code") == "SITT":
            marker = _sitting(item.get("title"))
            sittings.append((marker, [])) if marker else sittings.append(((date.min, 0, None), []))
            continue
        if sittings and (item.get("title") or "").strip():
            sittings[-1][1].append(item)
    todays = [(m, its) for m, its in sittings if m[0] == day]
    chosen: Optional[List[Dict[str, Any]]] = None
    if start is not None:
        exact = [its for m, its in todays if m[1] == start]
        within = [its for m, its in todays if m[2] is not None and m[1] <= start < m[2]]
        chosen = exact[0] if len(exact) == 1 else within[0] if len(within) == 1 else None
    if chosen is None and len(todays) == 1:
        chosen = todays[0][1]
    out = []
    for item in chosen or []:
        ref = (item.get("procedure_ref") or "").strip()
        out.append({"number": item.get("number"), "title": item["title"].strip(),
                    "procedure_refs": [ref] if ref else []})
    return out


_JOINT_EVENT = re.compile(r"-COMMITTEE-[A-Z]{3,5}-[A-Z]{3,5}", re.I)


def pick_sitting(agendas: List[Tuple[Optional[str], Optional[List[Dict[str, Any]]]]], committee: str,
                 event_id: Optional[str], day: date, start: Optional[int]) -> List[Dict[str, Any]]:
    """The one sitting a webstream shows among a committee's agendas, or [].

    `agendas` is [(meeting_reference, items)]. A committee's own agendas ('ITRE(2026)1110_1')
    and those of the joint committees it sits in ('CJ05(2026)1110_1') are held under the
    same committee code: a joint webstream (two committees in its event id) is read from the
    joint agendas, any other from the committee's own. The same list published twice is one.
    Still more than one: none, never a choice between them.
    """
    joint = bool(_JOINT_EVENT.search(event_id or ""))
    lists: List[List[Dict[str, Any]]] = []
    for reference, items in agendas:
        ref = (reference or "").upper()
        if joint != ref.startswith("CJ") or (not joint and not ref.startswith(committee.upper() + "(")):
            continue
        found = sitting_items(items, day, start)
        if found and [i["title"] for i in found] not in [[i["title"] for i in l] for l in lists]:
            lists.append(found)
    return lists[0] if len(lists) == 1 else []


def transcript_note(has_transcript: bool, institution: Optional[str], meeting_day: Optional[date],
                    today: date) -> Optional[str]:
    """Why a meeting has no transcript, in words; None when it has one."""
    if has_transcript:
        return None
    if meeting_day is not None and meeting_day >= today:
        return NOTE_NOT_HELD
    if (institution or "EP").upper() == "EP" and meeting_day is not None \
            and meeting_day >= RECORDINGS_CLOSED_FROM:
        return NOTE_CLOSED
    return NOTE_NONE


def attach_agendas(session, today: Optional[date] = None, limit: int = 400) -> int:
    """Give each Parliament committee meeting without agenda items its sitting's agenda.

    Read from ep_emeeting_agendas (same committee, dated the meeting's day or up to
    AGENDA_LOOKBACK_DAYS before it). Only an empty agenda is written, and the procedures the
    items name are stored when the row has none. Returns the number of meetings written.
    """
    from sqlalchemy import text
    today = today or datetime.utcnow().date()
    rows = session.execute(text(
        "SELECT id, committee_code, meeting_date, event_id, related_procedure_refs "
        "FROM committee_meeting_transcripts "
        "WHERE upper(coalesce(institution, 'EP')) = 'EP' AND committee_code <> 'PLENARY' "
        "  AND (agenda_items IS NULL OR agenda_items::text IN ('[]', 'null')) "
        "  AND meeting_date <= :soon "
        "ORDER BY meeting_date DESC LIMIT :lim"),
        {"soon": today + timedelta(days=14), "lim": limit}).fetchall()
    import json
    written = 0
    for row in rows:
        started = meeting_start(row.event_id)
        day = started[0] if started else row.meeting_date.date()
        agendas = session.execute(text(
            "SELECT meeting_reference, items FROM ep_emeeting_agendas WHERE committee_code = :c "
            "AND meeting_date BETWEEN :d0 AND :d1 ORDER BY meeting_date DESC"),
            {"c": row.committee_code, "d0": day - timedelta(days=AGENDA_LOOKBACK_DAYS), "d1": day}).fetchall()
        items = pick_sitting([(a.meeting_reference, a.items) for a in agendas], row.committee_code,
                             row.event_id, day, started[1] if started else None)
        if not items:                       # none, or several claiming the sitting: no guess
            continue
        refs = sorted({r for it in items for r in it["procedure_refs"]})
        session.execute(text(
            "UPDATE committee_meeting_transcripts SET agenda_items = CAST(:a AS json), "
            "related_procedure_refs = CASE WHEN coalesce(array_length(related_procedure_refs, 1), 0) = 0 "
            "                             THEN CAST(:r AS varchar[]) ELSE related_procedure_refs END "
            "WHERE id = :i AND (agenda_items IS NULL OR agenda_items::text IN ('[]', 'null'))"),
            {"a": json.dumps(items, ensure_ascii=False), "r": refs, "i": row.id})
        written += 1
    if written:
        session.commit()
    return written


def transcript_gap(session, today: Optional[date] = None) -> Dict[str, Any]:
    """How many Parliament committee meetings already held have no transcript, and the day of
    the last one transcribed."""
    from sqlalchemy import text
    today = today or datetime.utcnow().date()
    row = session.execute(text(
        "SELECT count(*) FILTER (WHERE coalesce(transcript_text, '') = '' AND meeting_date < :t) AS held_without, "
        "       max(meeting_date) FILTER (WHERE coalesce(transcript_text, '') <> '') AS last_transcribed "
        "FROM committee_meeting_transcripts "
        "WHERE upper(coalesce(institution, 'EP')) = 'EP' AND committee_code <> 'PLENARY'"),
        {"t": today}).one()
    return {"held_without": int(row.held_without or 0),
            "last_transcribed": row.last_transcribed.date() if row.last_transcribed else None}
