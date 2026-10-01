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
