#!/usr/bin/env python3.12
"""Ask each official's Whoiswho page whether it exists, and stop serving the dead ones.

GovClipping reported on 1 October 2026 that who-is-who URLs led to pages that do
not exist. Pointing every official at their own person page was verified on 6
officials, 6/6 returning 200, and shipped. Measured across the whole table
afterwards, roughly 4,400 of 17,777 (~25%) return 404.

There is no rule that predicts it. Whole families have no published person pages
(COR 0/13, ERCEA 0/10, EIB 0/10) while others are partial (EESC 1/10, HADEA 5/10),
the id carries no signal, and the SPARQL directory does not say. Existence can only
be established by asking the page, so this asks it once per official and stores the
answer in url_status.

SAFETY: a 403 or 429 is the Publications Office throttling us, not a missing person.
Those are never written and never null a URL -- the row is simply left unchecked for
the next run. A run where blocked responses dominate exits non-zero rather than
reporting a clean sweep, because the one way this job could do real damage is to
read a throttling wave as 4,000 people ceasing to exist.

Bounded and resumable: it does --limit rows per run, unchecked first then stalest,
so it can be run repeatedly (or scheduled) until the backlog clears.

    python3.12 scripts/verify_who_is_who_urls.py --limit 50 --rehearse
    python3.12 scripts/verify_who_is_who_urls.py --limit 2000 --apply
"""
from __future__ import annotations

import argparse
import pathlib
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import certifi  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

PERSON_PAGE = "https://op.europa.eu/en/web/who-is-who/person/-/person/{person_id}"
# A browser UA: the directory serves a bot challenge to anything that looks automated,
# and a challenge would otherwise be miscounted as a verdict about the person.
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}
BLOCKED = {403, 429, 503}

PICK = text(
    """
    SELECT id, person_uri, public_url
      FROM who_is_who_officials
     WHERE person_uri IS NOT NULL
       AND (url_checked_at IS NULL OR url_checked_at < now() - make_interval(days => :stale))
     ORDER BY url_checked_at NULLS FIRST, id
     LIMIT :lim
    """
)

RECORD_ALIVE = text(
    """
    UPDATE who_is_who_officials
       SET url_status = :st, url_checked_at = now(), public_url = :url
     WHERE id = :rid
    """
)

RECORD_DEAD = text(
    """
    UPDATE who_is_who_officials
       SET url_status = :st, url_checked_at = now(), public_url = NULL
     WHERE id = :rid
    """
)

PROGRESS = text(
    """
    SELECT count(*) FILTER (WHERE url_checked_at IS NOT NULL)            AS checked,
           count(*)                                                      AS total,
           count(*) FILTER (WHERE url_status = 200)                      AS alive,
           count(*) FILTER (WHERE url_status = 404)                      AS dead
      FROM who_is_who_officials
     WHERE person_uri IS NOT NULL
    """
)


def _database_url() -> str:
    env = pathlib.Path(__file__).resolve().parents[1] / ".env"
    m = re.search(r"^DATABASE_URL=(.*)$", env.read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL not found in backend/.env")
    return m.group(1).strip()


def _url_for(person_uri: str) -> str | None:
    pid = person_uri.rstrip("/").rsplit("/", 1)[-1].strip()
    if not pid or "UNDEFINED" in pid:
        return None
    return PERSON_PAGE.format(person_id=pid)


def _probe(url: str, ctx: ssl.SSLContext, pause: float) -> int | str:
    """The page's own answer, or a blocked/transport marker. Never a guess."""
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
                return r.status
        except urllib.error.HTTPError as e:
            if e.code in BLOCKED and attempt < 2:
                time.sleep(pause * 8 * (attempt + 1))
                continue
            return e.code
        except Exception as e:  # transport: treat as unknown, never as 404
            if attempt < 2:
                time.sleep(pause * 4)
                continue
            return type(e).__name__
    return "exhausted"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=500, help="rows this run (default 500)")
    ap.add_argument("--pause", type=float, default=1.0, help="seconds between probes")
    ap.add_argument("--stale", type=int, default=90, help="re-check after N days")
    args = ap.parse_args()

    engine = create_engine(_database_url())
    with engine.connect() as conn:
        before = conn.execute(PROGRESS).one()
        rows = list(conn.execute(PICK, {"lim": args.limit, "stale": args.stale}))

    print(f"[INFO] officials with a person id : {before.total}")
    print(f"[INFO] already checked            : {before.checked}  (alive {before.alive}, dead {before.dead})")
    print(f"[INFO] this run                   : {len(rows)}")
    if args.rehearse:
        for r in rows[:5]:
            print(f"   would probe {(_url_for(r.person_uri) or '(no page: placeholder id)')[-58:]}")
        print("[INFO] rehearsal only, nothing written")
        return 0

    ctx = ssl.create_default_context(cafile=certifi.where())
    seen: Counter = Counter()
    alive = dead = skipped = 0

    for i, r in enumerate(rows, 1):
        url = _url_for(r.person_uri)
        if url is None:
            # A placeholder id. Settled already; record it so it is never probed again.
            with engine.begin() as conn:
                conn.execute(RECORD_DEAD, {"rid": r.id, "st": 404})
            dead += 1
            seen["placeholder"] += 1
            continue

        status = _probe(url, ctx, args.pause)
        seen[status] += 1

        if status == 200:
            with engine.begin() as conn:
                conn.execute(RECORD_ALIVE, {"rid": r.id, "st": 200, "url": url})
            alive += 1
        elif status == 404:
            with engine.begin() as conn:
                conn.execute(RECORD_DEAD, {"rid": r.id, "st": 404})
            dead += 1
        else:
            # Blocked or a transport fault. Not an answer about this person: leave the
            # row unchecked so the next run asks again. Writing here is how a throttling
            # wave would turn into thousands of people wrongly erased.
            skipped += 1

        if i % 100 == 0:
            print(f"   ...{i}/{len(rows)}  alive={alive} dead={dead} skipped={skipped}", flush=True)
        time.sleep(args.pause)

    with engine.connect() as conn:
        after = conn.execute(PROGRESS).one()

    print(f"\n[INFO] probed    : {len(rows)}")
    print(f"[INFO] alive     : {alive}")
    print(f"[INFO] dead      : {dead}  (public_url cleared)")
    print(f"[INFO] skipped   : {skipped}  (blocked or transport; left for the next run)")
    print(f"[INFO] responses : {dict(seen)}")
    print(f"[INFO] checked   : {before.checked} -> {after.checked} of {after.total}")
    print(f"[INFO] remaining : {after.total - after.checked}")

    answered = alive + dead
    if answered == 0 and rows:
        print("[ERROR] not one row got an answer; the directory is refusing us, not empty")
        return 1
    if skipped > answered:
        print(f"[ERROR] {skipped} blocked against {answered} answered: throttled, so this "
              f"run's picture is not trustworthy. Re-run with a larger --pause.")
        return 1
    print("[OK] every answered row now reflects what its page actually returns")
    return 0


if __name__ == "__main__":
    sys.exit(main())
