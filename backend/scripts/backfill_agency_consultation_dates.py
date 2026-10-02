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

    python3.12 scripts/backfill_agency_consultation_dates.py --rehearse
    python3.12 scripts/backfill_agency_consultation_dates.py --apply
"""
from __future__ import annotations

import argparse
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

PICK = text("""SELECT id, source_body, full_description FROM public_consultations
                WHERE source = 'agency' AND start_date IS NULL AND coalesce(full_description,'') <> ''""")
STORE = text("UPDATE public_consultations SET start_date = :d, last_updated = now() "
             "WHERE id = :i AND start_date IS NULL")


def _db() -> str:
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL missing")
    return m.group(1).strip()


def _date(body: str, agency: str):
    for pat, fmt in PATTERNS.get(agency, []):
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
        d = _date(r.full_description, r.source_body)
        if d:
            found[r.id] = (r.source_body, d)
        else:
            miss[r.source_body] += 1
    print(f"[INFO] undated agency consultations with page text: {len(rows)}")
    print(f"[INFO] labelled date found: {len(found)} {dict(Counter(b for b, _ in found.values()))}")
    print(f"[INFO] no labelled date (left NULL): {dict(miss)}")
    if a.rehearse:
        for rid, (b, d) in list(found.items())[:8]:
            print(f"   {b:6} {d:%Y-%m-%d}")
        print("[INFO] rehearsal only, nothing written")
        return 0
    n = 0
    with eng.begin() as c:
        for rid, (b, d) in found.items():
            n += c.execute(STORE, {"d": d, "i": rid}).rowcount
    print(f"[INFO] stored: {n}")
    if rows and n == 0:
        print("[ERROR] nothing stored; this run proves nothing")
        return 1
    print("[OK] every stored date is the one the agency's page labels as the opening")
    return 0


if __name__ == "__main__":
    sys.exit(main())
