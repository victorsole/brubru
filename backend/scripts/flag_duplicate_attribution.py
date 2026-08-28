#!/usr/bin/env python3.12
"""
Flag social posts that are somebody else's words stored as the actor's own.

WHY (/social-eu, 27 August 2026). The actor sections of the social pulse rest on
one premise: `is_repost` separates what an actor SAID from what they AMPLIFIED.
X repost detection is a prefix match on `RT @`, and it is very good at that job:
of 4,547 posts beginning `RT @`, only 13 were mis-flagged, so the guard is 99.7%
effective.

The gap is the posts that carry no marker at all. A quote-tweet, or text copied
verbatim from another account, arrives through the syndication endpoint with
nothing to distinguish it from an original. Worked example: a Euronews
correspondent's report that Mark Carney would address the European Parliament
was stored twice under the same MEP -- once at 19:51 as `RT @JorgeLiboreiro`
(correctly flagged) and once at 16:51 with no prefix and `is_repost = false`,
i.e. credited to the MEP as his own statement.

The fetcher cannot fix this: it sees one account at a time and has no way to know
another account published the same words first. So this is a reconciliation pass
over what is already stored.

REPORT ONLY. It deliberately does NOT write.

The first version of this script did auto-flag, using "same text under two
different account_ids, earliest wins". The dry run killed it, and the failure is
worth keeping:

  * `account_id` is per PLATFORM, so Christophe Hansen posting the same sentence
    to X and to Bluesky looked like Hansen reposting Hansen. Same for the
    European Commission and Terry Reintke. Cross-posting is not amplification.
  * Saskia Bricmont and Terry Reintke published an identical heatwave statement
    minutes apart. That is a CO-SIGNED joint statement, not one MEP reposting
    another.
  * Eight EU Delegations published the same anti-trafficking campaign text. That
    is syndicated institutional comms, not a repost either.

Identical text has at least four causes and only one of them is a repost. No
text-only rule separates them, so a human reads this list. Auto-flagging would
have rewritten `is_repost` on legitimate original posts, which is the same class
of defect as the guard it was meant to fix: a transform confidently destroying
true data.

    python3.12 scripts/flag_duplicate_attribution.py --days 30
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys

logging.disable(logging.WARNING)

# Run as a script, sys.path[0] is scripts/, so `core.*` is not importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal  # noqa: E402
from sqlalchemy import text  # noqa: E402

# Normalise away the noise that makes identical text look different: the RT
# prefix itself, t.co links, whitespace, case, and a trailing ellipsis (the
# syndication endpoint truncates long reposts with a Unicode ellipsis).
_RT = re.compile(r"^RT @[A-Za-z0-9_]+:\s*")
_URL = re.compile(r"https?://\S+")
_WS = re.compile(r"\s+")


def normalise(txt: str) -> str:
    t = _RT.sub("", txt or "")
    t = _URL.sub("", t)
    t = _WS.sub(" ", t).strip().lower()
    return t.rstrip("…. ")


# ---------------------------------------------------------------------------
# Section C, added 28 August 2026 (/social-eu).
#
# Sections A and B group by CONTENT TEXT. That misses the larger and more
# damaging half of the problem, because it can only see posts whose text was
# stored identically. Grouping by the platform's OWN post id finds the rest.
#
# A platform post id is globally unique: one X status id belongs to exactly one
# tweet by exactly one account, and one YouTube video id to one video. So the
# SAME id under two different handles is not ambiguous the way identical text
# is -- at most one of them can be right, and the others carry a URL that was
# SYNTHESISED as `<platform>/<account being fetched>/<id>` and will not resolve
# to the account it names.
#
# Measured on the day this was written: 601 X status ids claimed by up to
# TWELVE handles each (1,564 rows), and 732 shared urls overall (1,924 of them
# YouTube). 1,560 of the 1,564 X rows carried `is_repost = False` and
# `original_author = NULL`, so the migration-219 repost guard did not fire on
# any of them -- which means every downstream surface that trusts that flag,
# including this skill's own pulse query, reads them as ORIGINAL statements.
# Roberta Metsola and Susana Solis Perez are both recorded as having written
# the same sentence at the same second under the same id.
#
# Still REPORT ONLY. The overwhelming pattern is institutional amplification
# (one Commission tweet across twelve delegation accounts, one EP tweet across
# every language account), which is a re-attribution job, not a deletion job.
# Deciding which handle is the true author needs the platform, not this script.
# ---------------------------------------------------------------------------
NATIVE_ID_SQL = """
    SELECT native_id, platform,
           count(*)                        AS rows,
           count(DISTINCT account_id)      AS accounts,
           count(*) FILTER (WHERE NOT is_repost) AS unflagged,
           string_agg(DISTINCT entity_name, ' | ' ORDER BY entity_name) AS who
    FROM (
      SELECT p.id, p.account_id, p.platform, p.is_repost, a.entity_name,
             CASE
               WHEN p.post_url ~ 'status/[0-9]+'  THEN substring(p.post_url from 'status/([0-9]+)')
               WHEN p.post_url ~ '[?&]v=[A-Za-z0-9_-]+' THEN substring(p.post_url from '[?&]v=([A-Za-z0-9_-]+)')
               ELSE NULL
             END AS native_id
      FROM social_posts p
      JOIN social_accounts a ON a.id = p.account_id
      WHERE p.posted_at >= now() - (:d || ' days')::interval
    ) t
    WHERE native_id IS NOT NULL
    GROUP BY 1, 2
    HAVING count(DISTINCT account_id) > 1
    ORDER BY count(DISTINCT account_id) DESC, count(*) DESC
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=30, help="window to reconcile (default 30)")
    ap.add_argument("--min-len", type=int, default=60,
                    help="ignore short posts: a shared slogan is not a repost (default 60 chars)")
    args = ap.parse_args()

    db = SessionLocal()
    rows = db.execute(text("""
        SELECT p.id, p.account_id, a.entity_name, a.handle, p.content, p.posted_at,
               p.is_repost, p.original_author, p.post_url
        FROM social_posts p
        JOIN social_accounts a ON a.id = p.account_id
        WHERE p.posted_at >= now() - (:d || ' days')::interval
        ORDER BY p.posted_at
    """), {"d": args.days}).mappings().all()

    groups: dict[str, list] = {}
    for r in rows:
        if not r["content"] or len(r["content"]) < args.min_len:
            continue
        groups.setdefault(normalise(r["content"]), []).append(r)

    cross_post, cross_actor = [], []
    for _key, posts in groups.items():
        if len(posts) < 2:
            continue
        earliest = posts[0]
        for p in posts[1:]:
            if p["is_repost"]:
                continue  # already correctly attributed by the RT-prefix guard
            if p["account_id"] == earliest["account_id"]:
                continue  # duplicate ingest on one account, a different problem
            # Split on ENTITY, not on account. The same person on two platforms
            # is one actor cross-posting, and must never be called a repost.
            if (p["entity_name"] or "").strip() == (earliest["entity_name"] or "").strip():
                cross_post.append((p, earliest))
            else:
                cross_actor.append((p, earliest))

    print(f"window: {args.days}d   posts scanned: {len(rows)}   "
          f"content groups: {len(groups)}")
    print()
    print(f"A. SAME ACTOR, different platform ({len(cross_post)}) -- NOT reposts.")
    print("   Cross-posting. Listed so nobody 'fixes' them into reposts.")
    for p, orig in cross_post[:10]:
        print(f"   - {p['entity_name'][:34]:34} {p['posted_at']:%m-%d %H:%M} "
              f"({p['post_url'].split('/')[2]}) <- {orig['posted_at']:%m-%d %H:%M} "
              f"({orig['post_url'].split('/')[2]})")
    if len(cross_post) > 10:
        print(f"   ... and {len(cross_post) - 10} more")

    print()
    print(f"B. DIFFERENT ACTORS, identical text ({len(cross_actor)}) -- NEEDS A HUMAN.")
    print("   Could be: a copied post (the defect), a co-signed joint statement,")
    print("   or one institutional campaign syndicated across delegations.")
    for p, orig in cross_actor[:20]:
        print(f"   - {p['entity_name'][:30]:30} {p['posted_at']:%m-%d %H:%M} "
              f"<- earlier: {orig['entity_name'][:28]} {orig['posted_at']:%m-%d %H:%M}")
        print(f"       {(p['content'] or '')[:92]!r}")
        print(f"       {p['post_url']}")
    if len(cross_actor) > 20:
        print(f"   ... and {len(cross_actor) - 20} more")

    dupes = db.execute(text(NATIVE_ID_SQL), {"d": args.days}).mappings().all()
    total_rows = sum(d["rows"] for d in dupes)
    unflagged = sum(d["unflagged"] for d in dupes)
    print()
    print(f"C. SAME PLATFORM POST ID, different actors ({len(dupes)} ids / "
          f"{total_rows} rows) -- NOT ambiguous.")
    print("   A platform post id is globally unique, so at most ONE handle per")
    print("   group is the real author and the rest carry a synthesised URL.")
    print(f"   {unflagged} of {total_rows} are NOT flagged is_repost, so every")
    print("   surface trusting that flag reads them as original statements.")
    for d in dupes[:15]:
        print(f"   - [{d['platform']}] id {d['native_id']}  "
              f"{d['accounts']} accounts / {d['rows']} rows")
        print(f"       {d['who'][:110]}")
    if len(dupes) > 15:
        print(f"   ... and {len(dupes) - 15} more")

    print()
    print("REPORT ONLY -- nothing written. Identical text has several innocent")
    print("causes; only a human can tell a copied post from a co-signed one.")
    print("Section C is not ambiguous about the FACT, only about the REMEDY:")
    print("the right fix is re-attribution to the true author, not deletion.")
    db.close()
    return 1 if dupes else 0


if __name__ == "__main__":
    sys.exit(main())
