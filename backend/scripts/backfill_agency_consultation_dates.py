#!/usr/bin/env python3.12
"""Read agency consultations' opening date from the text of their own page.

395 agency consultations had no start_date, so document_date was empty. Their page,
now stored in full_description by fetch_agency_consultation_text.py, states the date
under a label that differs by agency:

  EASA   "Starting date of initial consultation 07 Nov 2025"
  ACER   "Open: 21.11.2025"
  ERA    "Published: 10 January 2020"
  BEREC  "The public consultation will run from 14 June 2023 to 15 August 2023"
         "was open from Wednesday, 12 December 2018"
  SRB    the press release's own date line, "Monday, 01 December 2025"

Only a LABELLED date is taken. An unlabelled date in the text (a plenary meeting, a
deadline, a cited act) is never used as the opening date; such rows stay NULL.

Closing dates too (15 Oct 2026). GovClipping's contract is publication date, feedback
opens, feedback closes on every consultation; on 15 Oct 121 ACER, 109 EASA, 140 BEREC and
2 ERA rows had no closing date, and 138 BEREC rows no opening date. The labels:

  ACER   "Close: 16.09.2024"
  EASA   "Extended closing date of consultation 19/08/2024" (wins), "Closing date of
         consultation 08/12/2022", "Deadline for comments 15/05/2018"
  ERA    "Closing date 20 February 2018"
  BEREC  one sentence holds both, in a dozen spellings: "ran from 11 October to 8 November
         2017", "will run from 16 of March until 21 of April 2021", "Run from 14May to 3 June
         2013", "was open from Wednesday, 12 December 2018, at 14:00 CET to Friday, 18
         January 2019". An opening date without a year takes the closing date's (the year
         before when its month is later). A range with no year at all is left NULL.

Only empty columns are written. The agency sync (sync_agency_consultations.py) writes a
date only when its source gives one and never empties one, so these survive it.

    python3.12 scripts/backfill_agency_consultation_dates.py --rehearse
    python3.12 scripts/backfill_agency_consultation_dates.py --apply
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys
from collections import Counter
from datetime import datetime

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import create_engine, text  # noqa: E402

_MON = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
_DAY = r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+"
PATTERNS = {
    "EASA": [(r"Starting date of initial consultation\s+(\d{1,2} [A-Z][a-z]{2} \d{4})", "%d %b %Y")],
    "ACER": [(r"Open:\s*(\d{2}\.\d{2}\.\d{4})", "%d.%m.%Y")],
    "ERA": [(r"Published:\s*(\d{1,2} " + _MON + r" \d{4})", "%d %B %Y")],
    "BEREC": [(r"(?:run|runs|ran|open|opened)\s+from\s+(?:" + _DAY + r")?(\d{1,2} " + _MON + r" \d{4})", "%d %B %Y")],
    "SRB": [(r"^\s*" + _DAY + r"(\d{1,2} " + _MON + r" \d{4})", "%d %B %Y")],
}

END_PATTERNS = {
    "ACER": [(r"Close:\s*(\d{2}\.\d{2}\.\d{4})", "%d.%m.%Y")],
    "EASA": [(r"Extended closing date of consultation\s+(\d{2}/\d{2}/\d{4})", "%d/%m/%Y"),
             (r"Closing date of consultation\s+(\d{2}/\d{2}/\d{4})", "%d/%m/%Y"),
             (r"Deadline for comments\s+(\d{2}/\d{2}/\d{4})", "%d/%m/%Y")],
    "ERA": [(r"Closing date\s+(\d{1,2} " + _MON + r" \d{4})", "%d %B %Y")],
}
_MONTHS = {m.lower(): i for i, m in enumerate(
    "January February March April May June July August September October November December".split(), 1)}
_D = r"(?:" + _DAY + r")?(\d{1,2})(?:st|nd|rd|th)?\s*(?:of\s+)?(" + _MON + r")(?:,?\s+(\d{4}))?"
# The opening's month may be left out when both fall in one month ("from 1 to 30 March 2012").
_D_OPEN = (r"(?:" + _DAY + r")?(\d{1,2})(?:st|nd|rd|th)?\s*(?:of\s+)?(" + _MON + r")?(?:,?\s+(\d{4}))?")
_BEREC_RANGE = re.compile(
    r"\b(?:run|runs|ran|open|opened|held|launched|consultations?)\b[^.]{0,60}?\b(?:from|between)\s+"
    + _D_OPEN + r"[^.]{0,40}?\s(?:to|until|till|and)\s+" + _D + r"(?:[^.]{0,30}?\b((?:19|20)\d\d)\b)?",
    re.I)
# A deadline alone: "Stakeholders are invited to submit their inputs by 21 November 2019".
_BEREC_DEADLINE = re.compile(
    r"(?:\b(?:submit|send|provide|deliver)\b[^.]{0,100}?\bby|\bdeadline\b[^.]{0,40}?)\s+"
    r"(?:" + _DAY + r")?(\d{1,2})(?:st|nd|rd|th)?\s*(?:of\s+)?(" + _MON + r"),?\s+(\d{4})", re.I)

PICK = text("""SELECT id, source_body, full_description, start_date, end_date FROM public_consultations
                WHERE source = 'agency' AND (start_date IS NULL OR end_date IS NULL)
                  AND coalesce(full_description,'') <> ''""")
STORE = text("""UPDATE public_consultations
                   SET start_date = coalesce(start_date, :s), end_date = coalesce(end_date, :e)
                 WHERE id = :i AND (start_date IS NULL OR end_date IS NULL)""")


def _db() -> str:
    # The environment first: Railway has no .env file.
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    env = BACKEND / ".env"
    m = re.search(r"^DATABASE_URL=(.*)$", env.read_text(), re.M) if env.exists() else None
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL missing")
    return m.group(1).strip()


def berec_range(body: str):
    """(opens, closes) from BEREC's one sentence, or (None, None)."""
    for m in _BEREC_RANGE.finditer(body or ""):
        d1, m1, y1, d2, m2, y2, y_tail = m.groups()
        y2 = y2 or y_tail
        if not y2:
            continue
        mo2 = _MONTHS[m2.lower()]
        mo1 = _MONTHS[m1.lower()] if m1 else mo2
        y1 = int(y1) if y1 else (int(y2) if mo1 <= mo2 else int(y2) - 1)
        try:
            start, end = datetime(y1, mo1, int(d1)), datetime(int(y2), mo2, int(d2))
        except ValueError:
            continue
        if start <= end and (end - start).days <= 400 and 2005 <= start.year <= 2030:
            return start, end
    m = _BEREC_DEADLINE.search(body or "")
    if m:
        try:
            end = datetime(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
            if 2005 <= end.year <= 2030:
                return None, end
        except ValueError:
            pass
    return None, None


def _date(body: str, agency: str, patterns=None):
    for pat, fmt in (patterns or PATTERNS).get(agency, []):
        m = re.search(pat, body[:6000], flags=re.M)
        if m:
            try:
                return datetime.strptime(m.group(1), fmt)
            except ValueError:
                continue
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    eng = create_engine(_db(), pool_pre_ping=True)
    with eng.connect() as c:
        rows = list(c.execute(PICK))
    found, miss = {}, Counter()
    for r in rows:
        body, agency = r.full_description, r.source_body
        start = _date(body, agency) if r.start_date is None else None
        end = _date(body, agency, END_PATTERNS) if r.end_date is None else None
        if agency == "BEREC":
            s2, e2 = berec_range(body)
            start = start or (s2 if r.start_date is None else None)
            end = end or (e2 if r.end_date is None else None)
        if start or end:
            found[r.id] = (agency, start, end)
        else:
            miss[agency] += 1
    print(f"[INFO] agency consultations missing a date, with page text: {len(rows)}")
    print(f"[INFO] labelled date found: {len(found)} {dict(Counter(b for b, _, _ in found.values()))}")
    print(f"[INFO] no labelled date (left NULL): {dict(miss)}")
    if a.rehearse:
        for rid, (b, s_, e_) in list(found.items())[:12]:
            print(f"   {b:6} opens {s_:%Y-%m-%d} closes {e_:%Y-%m-%d}" if s_ and e_ else
                  f"   {b:6} opens {s_:%Y-%m-%d}" if s_ else f"   {b:6} closes {e_:%Y-%m-%d}")
        print("[INFO] rehearsal only, nothing written")
        return 0
    n = 0
    with eng.begin() as c:
        for rid, (b, s_, e_) in found.items():
            n += c.execute(STORE, {"s": s_.date() if s_ else None, "e": e_.date() if e_ else None,
                                   "i": rid}).rowcount
    print(f"[INFO] stored: {n}")
    # A night with nothing new to date is normal: rows without a labelled date stay as they are.
    print("[OK] every stored date is one the agency's page labels as the opening or closing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
