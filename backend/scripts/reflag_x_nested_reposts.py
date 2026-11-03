#!/usr/bin/env python3.12
"""
Re-flag X rows that are the tweet INSIDE a retweet, stored as the account's own post.

Until 3 Nov 2026 fetch_x walked into retweeted_status, so one native retweet produced two
rows: the outer "RT @author: text" (flagged) and the inner original (id, date, likes and text
of the original author, is_repost false, URL under this account's handle).

Rule, strict on purpose: an own row is re-flagged only if the SAME account also holds an
"RT @author: <same text>" row, the author is not the account itself, and the own row is not
later than the retweet. Text-only matching ACROSS accounts was rejected on 27 Aug 2026 (see
flag_duplicate_attribution.py): cross-posting and joint statements are not reposts. Quoted tweets
carry no RT row, so they are NOT caught here; the shared-id count printed at the end shows them.

Run it AFTER the fixed fetcher is deployed: the refresh list includes is_repost, so the old code
would write these rows back. Dry run by default; --apply writes in chunks by primary key.
"""
from __future__ import annotations

import argparse
import logging
import pathlib
import sys
import time

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
sys.path.insert(0, _REPO_ROOT + "/backend")

logging.disable(logging.CRITICAL)

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

CANDIDATES = r"""
WITH rt AS (
  SELECT p.account_id, p.original_author AS author, p.posted_at,
         regexp_replace(p.content, '^RT @[A-Za-z0-9_]+\s*:\s*', '') AS tail
    FROM social_posts p
   WHERE p.platform = 'x' AND p.is_repost AND p.content ~ '^RT @' AND p.original_author IS NOT NULL
)
SELECT DISTINCT ON (o.id) o.id, o.post_url, r.author,
       substring(o.post_url from 'status/([0-9]+)') AS sid, left(o.content, 70) AS head, a.entity_name
  FROM social_posts o
  JOIN rt r ON r.account_id = o.account_id
  JOIN social_accounts a ON a.id = o.account_id
 WHERE o.platform = 'x' AND NOT o.is_repost
   AND o.posted_at <= r.posted_at
   AND lower(r.author) <> lower(coalesce(substring(o.post_url from 'x\.com/([^/]+)/'), ''))
   AND (o.content = r.tail
        OR (right(r.tail, 1) = '…' AND length(r.tail) > 30 AND o.content LIKE replace(replace(left(r.tail, length(r.tail) - 1), '\', '\\'), '%', '\%') || '%'))
 ORDER BY o.id
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--chunk", type=int, default=200)
    ap.add_argument("--sample", type=int, default=12)
    args = ap.parse_args()
    db = SessionLocal()
    rows = db.execute(text(CANDIDATES)).mappings().all()
    own = db.execute(text("SELECT count(*) FROM social_posts WHERE platform='x' AND NOT is_repost")).scalar()
    print(f"own X rows: {own}; nested originals found: {len(rows)}")
    for r in rows[:: max(1, len(rows) // args.sample)][: args.sample]:
        print(f"  {r['entity_name'][:24]:<24} {r['sid']} really @{r['author']:<16} {r['head']!r}")
    if not args.apply:
        print("dry run, nothing written; --apply to write")
        return 0
    written = 0
    for i in range(0, len(rows), args.chunk):
        for r in rows[i:i + args.chunk]:
            res = db.execute(
                text("UPDATE social_posts SET is_repost = TRUE, original_author = :a, post_url = :u "
                     "WHERE id = :id AND NOT is_repost"),
                {"a": r["author"], "u": f"https://x.com/{r['author']}/status/{r['sid']}", "id": r["id"]},
            )
            written += res.rowcount
        db.commit()
        time.sleep(0.5)
    left = db.execute(text(
        "SELECT count(*) FROM social_posts WHERE platform='x' AND NOT is_repost")).scalar()
    shared = db.execute(text(
        """WITH x AS (SELECT account_id, is_repost, substring(post_url from 'status/([0-9]+)') sid
                        FROM social_posts WHERE platform='x'),
                s AS (SELECT sid FROM x GROUP BY sid HAVING count(DISTINCT account_id) > 1)
           SELECT count(*) FROM x JOIN s USING (sid) WHERE NOT is_repost""")).scalar()
    print(f"re-flagged: {written}; own X rows now: {left}; own rows still on a shared id (quotes, true authors): {shared}")
    db.close()
    return 0 if written or not rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
