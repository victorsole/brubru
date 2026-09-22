"""Created / updated windows for incremental sync (22 Sep 2026).

A partner that syncs every morning needs two things from a list endpoint: a date on
each item saying when Brubru first recorded it and when its content last changed, and
a filter on those dates, so "what changed since yesterday" is one bounded query rather
than a re-read of every page. This module is that contract, shared by every endpoint
that offers it:

* `created_from` / `created_to`: when Brubru first recorded the item.
* `updated_from` / `updated_to`: when the item's content last changed. A re-sync that
  finds the same content does NOT move it (enforced by the trigger in migration 234).
* A bare date as an upper bound covers that whole day (`UpperBoundDatetime`).
* `order=updated_asc` pages oldest-change-first with `id` as tie-break, the order to
  use when walking an incremental window, because a row updated while you page can
  only move to the END of the window, never skip a page.

A datetime without a timezone is read as UTC.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from ._date_bounds import UpperBoundDatetime  # noqa: F401  re-exported for handlers

SYNC_ORDERS = ("updated_asc", "updated_desc", "created_asc", "created_desc")

SYNC_PARAMS_DOC = (
    "- `created_from`, `created_to`: when Brubru first recorded the item (ISO date or datetime; "
    "a bare date as `_to` covers the whole day).\n"
    "- `updated_from`, `updated_to`: when the item's content last changed. A daily re-sync that "
    "finds the same content does not move this date, so `updated_from=<yesterday>` returns only "
    "what really changed.\n"
    "- `order=updated_asc` is the order to page an incremental window in (ties broken by `id`)."
)

SYNC_FIELDS_DOC = (
    "Every item carries `creation_date` (when Brubru first recorded it) and `updated_date` "
    "(when its content last changed)."
)


def utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def validate_window(created_from=None, created_to=None, updated_from=None, updated_to=None) -> Dict[str, Optional[datetime]]:
    """Normalise to UTC and reject an inverted window with a 422 that says which one."""
    w = {"created_from": utc(created_from), "created_to": utc(created_to),
         "updated_from": utc(updated_from), "updated_to": utc(updated_to)}
    for lo, hi in (("created_from", "created_to"), ("updated_from", "updated_to")):
        if w[lo] and w[hi] and w[lo] > w[hi]:
            raise HTTPException(status_code=422, detail={
                "reason_code": "invalid_date_range",
                "message": f"`{lo}` ({w[lo].isoformat()}) is after `{hi}` ({w[hi].isoformat()}).",
            })
    return w


def any_window(w: Dict[str, Optional[datetime]]) -> bool:
    return any(v is not None for v in w.values())


def sql_window(where: List[str], params: Dict[str, Any], w: Dict[str, Optional[datetime]],
               created_col: str, updated_col: str) -> None:
    """Append the window to a raw-SQL WHERE list (infringements style)."""
    for key, col, op in (("created_from", created_col, ">="), ("created_to", created_col, "<="),
                         ("updated_from", updated_col, ">="), ("updated_to", updated_col, "<=")):
        if w.get(key) is not None:
            where.append(f"{col} {op} :{key}")
            params[key] = w[key]


def orm_window(query, w: Dict[str, Optional[datetime]], created_col, updated_col):
    """Apply the window to a SQLAlchemy query."""
    if w.get("created_from") is not None:
        query = query.filter(created_col >= w["created_from"])
    if w.get("created_to") is not None:
        query = query.filter(created_col <= w["created_to"])
    if w.get("updated_from") is not None:
        query = query.filter(updated_col >= w["updated_from"])
    if w.get("updated_to") is not None:
        query = query.filter(updated_col <= w["updated_to"])
    return query


def sql_order(order: str, created_col: str, updated_col: str, id_col: str = "id") -> Optional[str]:
    """ORDER BY for a sync order, or None when `order` is not one of them."""
    col = {"updated": updated_col, "created": created_col}.get(order.split("_")[0]) if order in SYNC_ORDERS else None
    if col is None:
        return None
    d = "ASC" if order.endswith("_asc") else "DESC"
    return f"{col} {d}, {id_col} {d}"


def orm_order(order: str, created_col, updated_col, id_col):
    if order not in SYNC_ORDERS:
        return None
    col = updated_col if order.startswith("updated") else created_col
    if order.endswith("_asc"):
        return (col.asc(), id_col.asc())
    return (col.desc(), id_col.desc())
