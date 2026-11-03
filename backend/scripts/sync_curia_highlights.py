#!/usr/bin/env python3.12
"""
Turn the Court of Justice's weekly #ECJHighlights post into calendar rows.

The Court posts its coming opinions and judgments days ahead, in one line each:
    "03/11 (O): Can #AI chatbots reproduce parts of news articles? (C-250/25)"
It named the Like Company opinion on 30 Oct 2026, four days before delivery; nothing else
we read looks forward like this. eu_calendar_events held no Court row for that week.

Reads social_posts (the Court's Mastodon account, already fetched by /social-eu and the cron),
writes eu_calendar_events. Idempotent on external_id. Only dates from today on: a past line
is not a calendar item. A line is what the Court announced, never an outcome.

Dry run by default; --apply writes. Exits 1 if the account has no recent post at all, so a dead
feed cannot read as "the Court announced nothing".
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import pathlib
import re
import sys
import uuid

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
sys.path.insert(0, _REPO_ROOT + "/backend")

_LINE = re.compile(r"(\d{2})/(\d{2})\s*\(([OJ])\)\s*:\s*(.+?)\s*\((C-\d+/\d{2}(?:\s*(?:and|,)\s*C-\d+/\d{2})*)\)")
_KIND = {"O": "Advocate General's opinion", "J": "judgment"}


def parse_post(content: str, posted: dt.date) -> list[dict]:
    """Lines of one #ECJHighlights post. The year comes from the post: 28/12 posted in January is last year's."""
    text = re.sub(r"#\s+(\w)", r"#\1", content or "")
    text = re.sub(r"#(\w+)", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    out = []
    for dd, mm, kind, what, case in _LINE.findall(text):
        what = re.sub(r"[^\w\s.,;:'?!()/%&-]", "", what).strip()
        year = posted.year
        day = dt.date(year, int(mm), int(dd))
        if (day - posted).days < -180:
            day = dt.date(year + 1, int(mm), int(dd))
        out.append({"date": day, "kind": kind, "what": what, "case": case})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--days", type=int, default=14, help="how far back to read posts")
    args = ap.parse_args()
    logging.disable(logging.CRITICAL)
    from sqlalchemy import text

    from core.database import SessionLocal

    db = SessionLocal()
    posts = db.execute(text(
        """SELECT p.content, p.posted_at, p.post_url FROM social_posts p JOIN social_accounts a ON a.id = p.account_id
            WHERE p.post_url LIKE '%curia.social-network.europa.eu/@Curia/%'
              AND p.posted_at >= now() - make_interval(days => :d)
            ORDER BY p.posted_at"""), {"d": args.days}).mappings().all()
    if not posts:
        print("[ERROR] no Court post in the window: the feed is not being read, this is not a quiet week")
        return 1
    today = dt.date.today()
    found = written = 0
    for p in posts:
        if "ECJHighlights" not in re.sub(r"\s+", "", p["content"] or ""):
            continue
        for item in parse_post(p["content"], p["posted_at"].date()):
            if item["date"] < today:
                continue
            found += 1
            title = f"Court of Justice {_KIND[item['kind']]}: {item['what']} ({item['case']})"
            ext = f"curia_highlight_{item['case'].lower().replace('/', '_').replace(' ', '')}_{item['date'].isoformat()}"
            exists = db.execute(text("SELECT 1 FROM eu_calendar_events WHERE external_id = :x"), {"x": ext}).first()
            print(("SKIP " if exists else "ADD  "), item["date"], title[:95])
            if exists or not args.apply:
                continue
            desc = (f"Announced in the Court's own week-ahead post. {_KIND[item['kind']].capitalize()} scheduled; "
                    "no outcome is known from this entry.")
            db.execute(text(
                """INSERT INTO eu_calendar_events (id, institution, event_type, title, description, start_date, end_date,
                       all_day, policy_areas, status, source_url, procedure_refs, related_documents, source, external_id,
                       scraped_at, first_seen, last_updated, organiser)
                   VALUES (:id, 'ECJ', 'special_date', :t, :ds, :d, :d, true, :pa, 'scheduled', :u, :pr, cast('{}' as jsonb),
                       'curia_highlights', :x, now(), now(), now(), 'Court of Justice of the European Union')"""),
                {"id": str(uuid.uuid4()), "t": title, "ds": desc, "d": item["date"], "pa": ["justice"],
                 "u": p["post_url"], "pr": [], "x": ext})
            written += 1
    if args.apply:
        db.commit()
    print(f"posts read: {len(posts)}; upcoming lines: {found}; written: {written}")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
