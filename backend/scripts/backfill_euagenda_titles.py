"""
Repair euagenda calendar rows whose title is a topic badge, not an event name.

Why (calendar audit, 3 September 2026)
--------------------------------------
`euagenda_scraper.py` in --no-details mode took the title from the FIRST text
line of a listing card, skipping only the "BOOSTED" marker. On euagenda that
first line is sometimes the topic badge, so My EU Calendar carries 126 rows
titled "Agriculture", "Energy", "Regions", "Science"...

These are NOT duplicates. Two genuinely different events on 5 May 2026 -- the
Second EU Rural Innovation Forum and a Baltic smart-villages conference -- were
both stored as "Agriculture", which made them look identical to any grouping on
(title, start_date). Deleting on that key would have destroyed real events; the
titles are what is wrong.

The scraper is fixed. This repairs the rows it already wrote, deriving the title
from the event's own URL slug.

Usage:
    python3.12 scripts/backfill_euagenda_titles.py --dry-run   # default
    python3.12 scripts/backfill_euagenda_titles.py --apply
"""
import argparse
import os
import pathlib
import re
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(_REPO_ROOT, "backend"))
from services.scrapers.euagenda_scraper import (  # noqa: E402
    _EUAGENDA_TOPIC_BADGES,
    _title_from_slug,
)


def _slug_from_url(url: str) -> str:
    """euagenda.eu/events/YYYY/MM/DD/<slug> -> <slug>"""
    if not url:
        return ""
    m = re.search(r"/events/\d{4}/\d{2}/\d{2}/([^/?#]+)", url)
    return m.group(1) if m else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="perform the writes (default is dry-run)")
    ap.add_argument("--dry-run", action="store_true", default=True)
    args = ap.parse_args()

    load_dotenv(os.path.join(_REPO_ROOT, "backend", ".env"))
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("[ERROR] DATABASE_URL not set; aborting rather than guessing.")
        return 2

    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id::text, title, source_url, external_id, start_date::date
        FROM eu_calendar_events
        WHERE source = 'euagenda' AND lower(title) = ANY(%s)
        ORDER BY start_date
        """,
        (sorted(_EUAGENDA_TOPIC_BADGES),),
    )
    rows = cur.fetchall()
    print(f"rows with a badge-shaped title: {len(rows)}")

    planned, unfixable = [], []
    for rid, title, src_url, ext_id, day in rows:
        slug = _slug_from_url(src_url or "")
        if not slug and ext_id:
            # external_id is euagenda:YYYY-MM-DD-<slug>
            m = re.match(r"euagenda:\d{4}-\d{2}-\d{2}-(.+)$", ext_id)
            slug = m.group(1) if m else ""
        new_title = _title_from_slug(slug)
        if new_title and new_title.lower() != (title or "").lower():
            planned.append((rid, title, new_title, day))
        else:
            unfixable.append((rid, title, src_url, day))

    print(f"  repairable: {len(planned)}   no usable slug: {len(unfixable)}")
    for _rid, old, new, day in planned[:12]:
        print(f"   {day}  {old!r:16} -> {new!r}")
    for _rid, old, src, day in unfixable[:5]:
        print(f"   [SKIP] {day} {old!r} url={src!r}")

    if not args.apply:
        print("\n[DRY-RUN] nothing written. Re-run with --apply to perform the writes.")
        return 0

    for rid, _old, new, _day in planned:
        cur.execute("UPDATE eu_calendar_events SET title = %s WHERE id::text = %s", (new, rid))
    conn.commit()

    # Verify by query. Silence is not success.
    cur.execute(
        "SELECT count(*) FROM eu_calendar_events WHERE source='euagenda' AND lower(title) = ANY(%s)",
        (sorted(_EUAGENDA_TOPIC_BADGES),),
    )
    remaining = cur.fetchone()[0]
    print(f"[OK] repaired {len(planned)} titles. Badge-titled rows remaining: {remaining}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
