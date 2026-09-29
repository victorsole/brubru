#!/usr/bin/env python3
"""Run the Tenderator matcher as its own process (29 Sep 2026).

Until today the matcher ran inside the web process (an APScheduler job at 05:00
UTC, services/schedulers/tender_match_scheduler.py). It loads every open tender
(~34,900) and scores it against every active profile, and the memory it grew
stayed with the web container for the rest of the day, billed by the minute:
measured on Railway, the container idles at 0.54 GB and sat at ~2 GB after the
scheduled work. Run here, as a daily-tier subprocess, the memory is returned
when the process exits.

It now runs right after the SEDIA ingest and the EU-institution tender bridge,
so the day's institution notices are matchable the same morning, and before the
07:30 UTC tender digest. The daily tier records the run under the key
`tender_matching`; the in-process scheduler is off unless
ENABLE_TENDER_MATCH_SCHEDULER=true.

    python3.12 scripts/run_tender_matching_daily.py

(scripts/run_tender_matching.py is the older manual CLI for one user or profile.)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal  # noqa: E402
from services.tenders.matcher import TenderMatcher  # noqa: E402


def main() -> int:
    db = SessionLocal()
    try:
        matcher = TenderMatcher(db)
        created = asyncio.run(matcher.match_all_users())
        # match_all_users commits and returns the number of rows it ADDED.
        print(f"[OK] tender matching: {created} new match(es)", flush=True)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
