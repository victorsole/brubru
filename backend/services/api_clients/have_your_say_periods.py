"""Which feedback period of a Have Your Say initiative a record describes, and its status.

ONE rule for every reader of a portal record (23 Oct 2026). It lived in
scripts/sync_have_your_say.py, the owner of the consultation status column, and
services/api_clients/have_your_say_client.py kept its own copy "the SAME rule" that was
never updated when the owner's changed on 29 Sep: the client still trusted the portal's
OPEN flag after the published deadline. Initiative 14569 (plant pests) closed on 22 Oct
23:59; on 23 Oct the owner read it closed and the client open, the test comparing them
failed on main, and the daily sync_consultations job (which writes OPEN onto existing
rows) would have reopened it each night until the portal flipped its flag. Both now call
the functions below; nothing else in the backend reads `receivingFeedbackStatus` for a
status.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional


def parse_portal_date(v: Optional[str]) -> Optional[date]:
    if not v:
        return None
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None


# The feedback exercise each stage IS. These are the values the API has documented all
# along (`public_consultation / call_for_evidence / feedback / roadmap / initiative`);
# only the first two were ever written, and everything else fell back to "initiative".
PERIOD_TYPE = {
    "OPC_LAUNCHED": "public_consultation",   # an open public consultation
    "PLANNING_WORKFLOW": "call_for_evidence",
}

# When more than one period is open, the type is the most specific exercise running.
# 5 initiatives of 4,108 have two open at once and every one of them is this pair, so
# the order below is the whole of the ambiguity, not a guess at a general rule.
TYPE_RANK = ["OPC_LAUNCHED", "PLANNING_WORKFLOW"]


def period_type(statuses: list, status: str, today: date) -> str:
    """The exercise the row's OWN period is, not whichever entry came first.

    status, start and end already describe one chosen period; the type was still read
    off `currentStatuses[0]`. Initiative 19293 carries a call for evidence and a public
    consultation OPEN together on the same 14 December window, so it was served as a
    call for evidence while the public consultation was the thing people could answer.
    """
    live = [s for s in statuses if s.get("receivingFeedbackStatus") == "OPEN"]
    pool = live if (status == "open" and live) else statuses
    named = [s.get("frontEndStage") for s in pool
             if s.get("frontEndStage") in PERIOD_TYPE]
    if not named:
        return "initiative"
    named.sort(key=lambda st: TYPE_RANK.index(st) if st in TYPE_RANK else len(TYPE_RANK))
    return PERIOD_TYPE[named[0]]


def pick_period(statuses: list, today: date):
    """One feedback period, and its status and BOTH its dates, taken together.

    An initiative has several feedback periods (a call for evidence, then a public
    consultation, sometimes a planned one). Until 29 Sep 2026 the status was "OPEN if
    ANY period is open" while start and end were the first non-null of each across ALL
    periods, so a row could carry an open status beside the end date of a period that
    closed weeks earlier. Initiative 18892 (Revision of the EIT Regulation) was stored
    open with end_date 23 Sep, which is the end of its CLOSED call for evidence, while
    the portal's next period is UPCOMING from 1 Oct. Four more rows were 'open' past
    their own end date, and one 'closed' row had an end date in the future.

    A record must describe ONE period. Preference: the period actually open now, else
    the one about to open, else the one that closed most recently.

    Returns (status, start, end), all three from the SAME period.
    """
    def end_of(s):
        return parse_portal_date(s.get("feedbackEndDate"))

    def out(s, status):
        start, end = parse_portal_date(s.get("feedbackStartDate")), end_of(s)
        # The portal itself publishes one impossible pair: initiative 14641 ("Clean
        # corporate vehicles") has a feedback period starting 18 December 2025 and
        # ending 2 April 2025. A start after its own end is not a start date, so it is
        # dropped here, where the record is read, rather than written and cleaned up
        # afterwards (which reported a repair on every run, for ever).
        if start and end and start > end:
            start = None
        return status, start, end

    live = [s for s in statuses if s.get("receivingFeedbackStatus") == "OPEN"]
    # An OPEN period whose deadline has passed is the portal being slow to flip its own
    # flag: the deadline it publishes is the fact, so it reads as closed here.
    current = [s for s in live if (end_of(s) or today) >= today]
    if current:
        return out(sorted(current, key=lambda s: (not s.get("isCurrent"),))[0], "open")
    if live:
        return out(max(live, key=lambda s: end_of(s) or date.min), "closed")

    # UPCOMING is a claim about the future and needs a window that has not already
    # passed. The portal keeps periods it planned and never ran: initiative 12131 is
    # still UPCOMING with a planned window of January to March 2020. Serving that as
    # forthcoming six years later is the same defect as serving a closed consultation
    # as open, so a planned window that has ended does not make a row upcoming.
    upcoming = [s for s in statuses if s.get("receivingFeedbackStatus") == "UPCOMING"]
    dated = [s for s in upcoming if end_of(s)]
    ahead = [s for s in dated if end_of(s) >= today]
    if ahead:
        return out(min(ahead, key=end_of), "upcoming")
    if dated:
        # Every planned window has already passed: it did not happen. Reported closed
        # with the last window published, never as still forthcoming.
        return out(max(dated, key=end_of), "closed")
    if upcoming:
        # Planned, no window published: nothing contradicts "upcoming", so say it and
        # carry no dates rather than borrowing another period's.
        return out(upcoming[0], "upcoming")

    closed = [s for s in statuses if s.get("receivingFeedbackStatus") == "CLOSED"]
    if closed:
        return out(max(closed, key=lambda s: end_of(s) or date.min), "closed")
    return None, None, None
