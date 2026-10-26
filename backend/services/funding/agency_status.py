"""The status of an EU body's own procurement item in economy_items (26 Oct 2026).

Tenders, grants, calls for expression of interest and calls that EU bodies publish on their own
sites (item_type tender | grant | eoi_call | call | framework). Most writers had the status and
the deadline in hand and put them only into the text ("Status: Open", "Deadline: 2026-08-31"):
on 26 Oct 388 such items had no status and none a deadline (310 tenders, grants and calls for
expression of interest, 341 of those on 20 Oct; 49 calls; 29 framework contracts), and 17 lists
did not serve the fields at all. One rule, as for TED and the F&T calls: the dates win over the word.

    deadline day passed                          -> closed
    the body says closed, awarded, cancelled ... -> closed
    the body says upcoming or forthcoming        -> forthcoming
    the body says open, or a deadline is ahead   -> open
    otherwise                                    -> None (not stated)

A deadline day still counts as open: SEDIA stores the day at 00:00 and the cut-off is in the
afternoon. `close_passed` is the daily pass, since a writer reads only what its body still lists.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import text

ITEM_TYPES = ("tender", "grant", "eoi_call", "call", "framework")

_CLOSED = {"closed", "awarded", "cancelled", "canceled", "expired", "completed", "unfruitful",
           "evaluation", "under evaluation", "in progress", "archived"}
_FORTHCOMING = {"forthcoming", "upcoming", "planned", "prior information notice"}
_OPEN = {"open", "ongoing", "active", "open for submission"}


def from_source(word: Optional[str], deadline: Optional[datetime], today: date) -> Optional[str]:
    """open | forthcoming | closed from the body's own word and the deadline, or None."""
    if deadline is not None and deadline.date() < today:
        return "closed"
    w = (word or "").strip().lower()
    if w in _CLOSED:
        return "closed"
    if w in _FORTHCOMING:
        return "forthcoming"
    if w in _OPEN or deadline is not None:
        return "open"
    return None


_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"], 1)}
_MONTH = r"(january|february|march|april|may|june|july|august|september|october|november|december)"
_DATES = (
    (re.compile(r"\b(\d{1,2})\s?(?:st|nd|rd|th)?\s+" + _MONTH + r",?\s+(\d{4})", re.I), "dmy_name"),
    (re.compile(_MONTH + r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", re.I), "mdy_name"),
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "ymd"),
    (re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b"), "dmy"),
)


def _first_date(s: str) -> Optional[Tuple[int, datetime]]:
    """The earliest date written in `s` (day before month in numeric dates, as EU bodies write
    them) and where it starts."""
    found = []
    for rx, kind in _DATES:
        m = rx.search(s)
        if not m:
            continue
        g = m.groups()
        try:
            if kind == "dmy_name":
                d = datetime(int(g[2]), _MONTHS[g[1].lower()], int(g[0]), tzinfo=timezone.utc)
            elif kind == "mdy_name":
                d = datetime(int(g[2]), _MONTHS[g[0].lower()], int(g[1]), tzinfo=timezone.utc)
            elif kind == "ymd":
                d = datetime(int(g[0]), int(g[1]), int(g[2]), tzinfo=timezone.utc)
            else:
                d = datetime(int(g[2]), int(g[1]), int(g[0]), tzinfo=timezone.utc)
        except ValueError:
            continue
        found.append((m.start(), d))
    return min(found, key=lambda x: x[0]) if found else None


_DEADLINE = re.compile(r"\b(?:deadline|closing date|time[- ]limit)\b", re.I)
_SAYS_CLOSED = re.compile(r"\b(?:is|are|has been|now)\s+closed\b|\bhas (?:passed|expired)\b", re.I)


def deadline_in_text(txt: Optional[str]) -> Tuple[Optional[datetime], bool]:
    """(the first deadline the text labels as one, whether the text says that deadline is
    closed). Only a date that follows the word deadline (or closing date, time limit) within one
    stretch of 120 characters counts: a page also prints publication and award dates."""
    s = re.sub(r"\s+", " ", txt or "")
    for m in _DEADLINE.finditer(s):
        window = s[m.end():m.end() + 120]
        if _SAYS_CLOSED.search(window[:80]):
            return None, True
        hit = _first_date(window)
        if hit:
            return hit[1], False
    return None, False


_ECL_STATUS = re.compile(r"\bStatus\s*:?\s*(Open|Closed|Upcoming|Forthcoming|Ongoing)\b", re.I)
# Upper-case start, any case after: HaDEA's two-stage topics end "-01-two-stage".
_ECL_REFERENCE = re.compile(r"\bReference\s*:?\s*([A-Z][A-Z0-9][A-Za-z0-9/._\-]{4,60})")


def page_facts(txt: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[datetime]]:
    """(status word, reference, deadline) as an item page labels them ("Status Upcoming",
    "Reference HADEA/2026/OP/0020", "Deadline date 15 October 2026"), each None when unlabelled."""
    s = re.sub(r"\s+", " ", txt or "")
    st = _ECL_STATUS.search(s)
    ref = _ECL_REFERENCE.search(s)
    deadline, says_closed = deadline_in_text(s)
    word = "closed" if says_closed else (st.group(1) if st else None)
    return word, (ref.group(1).rstrip(".") if ref else None), deadline


_PASSED = ("item_type = ANY(CAST(:types AS text[])) AND status IN ('open', 'forthcoming') "
           "AND deadline::date < CURRENT_DATE")


def close_passed(db, *, apply: bool) -> int:
    """Close every open or forthcoming item whose deadline day has passed; returns the count.
    A status change is a real change, so the row's updated_at moves (its trigger)."""
    params = {"types": list(ITEM_TYPES)}
    n = db.execute(text(f"SELECT count(*) FROM economy_items WHERE {_PASSED}"), params).scalar() or 0
    if apply and n:
        db.execute(text(f"UPDATE economy_items SET status = 'closed' WHERE {_PASSED}"), params)
        db.commit()
    return n
