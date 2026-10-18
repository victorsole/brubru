"""The row-level timestamps every API item carries.

GovClipping asked on 1 October 2026 for each document to carry its own updated
timestamp: the envelope echoes `updated_from` / `updated_to`, and the items it
filtered carried only `creation_date`, so a client could not see the value it had
just filtered on, nor tell which rows in a page had actually moved.

It was never one endpoint. 102 of the 121 item models that expose `creation_date`
had no updated counterpart.

The column holding that timestamp is not the same everywhere -- the corpus grew a
table at a time -- so it is resolved by asking the row rather than by assuming a
name. Order matters: `updated_at` is the trigger-maintained change signal where it
exists, and the others are the older spellings of the same idea.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

# Ordered most to least authoritative. `updated_at` is the column the
# brubru_touch_if_changed trigger maintains, so it is the real change signal; the rest
# predate it on tables that were never migrated to that name.
_UPDATED_COLUMNS = ("updated_at", "last_updated", "updated_date", "modified_at")

# Deliberately NOT in that list: scraped_at, fetched_at, first_seen, created_at.
# A scrape or import timestamp says when WE touched the row, not when the document
# changed, and serving it as the change signal is how date filters end up answering
# from a handful of rows.


def row_updated(row: Any) -> Optional[datetime]:
    """The row's own last-updated timestamp, or None when it keeps none.

    Returns None rather than falling back to a creation or scrape time. A client
    syncing on this value needs an empty field to mean "this row records no change
    signal"; a creation date dressed up as one would quietly re-send rows that never
    moved, and hide ones that did.
    """
    if row is None:
        return None
    if isinstance(row, dict):
        for name in _UPDATED_COLUMNS:
            v = row.get(name)
            if v is not None:
                return v
        return None
    for name in _UPDATED_COLUMNS:
        v = getattr(row, name, None)
        if v is not None:
            return v
    return None


# The row's creation anchor, in the order the tables spell it. `first_seen` and
# `created_at` are pinned by the brubru_touch_if_changed trigger, so they never move
# on a re-fetch; `creation_date` is the economy tables' name for the same thing.
_CREATED_COLUMNS = ("first_seen", "created_at", "creation_date")


def row_created(row: Any) -> Optional[datetime]:
    """The row's own creation timestamp, or None when it keeps none.

    Never falls back to `last_updated`, `updated_at` or `scraped_at`. Six routes did
    exactly that (16 Oct 2026: questions, adopted and tabled texts, TRIS, votes), so a
    client saw `creation_date` move every night on 4,696 questions, 141 tabled texts,
    112 votes, 100 adopted texts and 75 TRIS notifications that had merely been
    re-fetched, and could not tell a new row from an old one.
    """
    if row is None:
        return None
    created = None
    get = row.get if isinstance(row, dict) else (lambda name: getattr(row, name, None))
    for name in _CREATED_COLUMNS:
        v = get(name)
        if v is not None:
            created = v
            break
    # A row cannot have been created after it last changed. 1,105 EPRS rows were deleted
    # and re-inserted by the text backfill of 15 Oct 2026 (14:42 UTC): their first_seen is
    # that re-insert while their last change, carried over, is earlier, and the change
    # trigger pins first_seen. Served as is, every one read "created after updated".
    updated = row_updated(row)
    if created is not None and updated is not None:
        try:
            if updated < created:
                return updated
        except TypeError:  # naive against aware: two different clocks, keep the anchor
            pass
    return created
