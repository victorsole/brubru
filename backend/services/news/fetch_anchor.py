"""Stamp the last-fetch anchor on eu_news_items rows a sync has just seen.

Why this is a helper and not an ORM listener
--------------------------------------------
`eu_news_items.fetched_at` (migration 229) must record when a sync last SAW a row on
its source listing, including rows it leaves otherwise unchanged. Every writer's
upsert has an early return on that path:

    if existing:
        ... nothing differs ...
        return "skipped"          # no UPDATE, so no before_update event

so a `before_update` listener -- the mechanism that composes body_txt for these same
writers -- never fires for exactly the rows that matter most. A body fetched
successfully every hour was indistinguishable from one nobody was reading, which is
how Council news went 70 days without a row while the nightly job recorded `success`
352 times.

Why one bulk statement per source
---------------------------------
Stamping row by row would mean an UPDATE per item per run. One `WHERE entry_key = ANY`
covers the whole sighting in a single statement, and `max(fetched_at)` per body is the
only thing /api/v2/news/latest reads.

Deliberately NOT `now()` in Python
----------------------------------
The stamp is `now()` evaluated by Postgres, so every row in a run shares one instant
and the value cannot drift with the app server's clock.
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session


def stamp_fetched(db: Session, entry_keys: Iterable[str]) -> int:
    """Set `fetched_at = now()` on every eu_news_items row with one of `entry_keys`.

    Returns the number of rows stamped. Callers should pass EVERY key the run saw,
    not only the ones it changed -- that distinction is the bug this exists to fix.

    Commits nothing: the caller owns the transaction, so the stamp lands with the
    rows it describes rather than in a separate one that could survive a rollback.
    """
    keys = [k for k in (entry_keys or []) if k]
    if not keys:
        return 0
    res = db.execute(
        text("UPDATE eu_news_items SET fetched_at = now() WHERE entry_key = ANY(:keys)"),
        {"keys": keys},
    )
    return res.rowcount or 0
