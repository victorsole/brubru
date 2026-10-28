"""The funding standard's shared pieces (proposal of 23 Oct 2026, Phase 2: one name and one parameter
set for every funding list).

Victor's decisions of 23 Oct 2026: bodies included by default (`include_body=true`), 50 items per
page, at most 200 (a list that allowed more keeps its maximum until the legacy date).
"""
from __future__ import annotations

from datetime import date
from typing import Optional, Tuple

from fastapi import HTTPException, Query

from api.v1._change_window import SYNC_ORDERS, sql_order

INCLUDE_BODY_DOC = "Return body_txt / body_html on every item of the list (default true)."


def include_body_param():
    """The `include_body` query parameter of a funding list: on unless the caller turns it off."""
    return Query(True, description=INCLUDE_BODY_DOC)


def without_bodies(envelope, include_body: bool):
    """A list answered with include_body=false: its items without body_txt / body_html. For the lists
    whose handler always composes the body (the v1 handlers behind the F&T and TED routes)."""
    if include_body:
        return envelope
    for item in getattr(envelope, "data", None) or []:
        for field in ("body_txt", "body_html"):
            if isinstance(item, dict):
                if field in item:
                    item[field] = None
            elif hasattr(item, field):
                setattr(item, field, None)
    return envelope


def published_window(
    published_from: Optional[date] = Query(None, description="Published on or after (YYYY-MM-DD); `since` and `from` are aliases."),
    published_to: Optional[date] = Query(None, description="Published on or before (YYYY-MM-DD); `until` and `to` are aliases."),
    since: Optional[date] = Query(None, include_in_schema=False),
    until: Optional[date] = Query(None, include_in_schema=False),
    from_: Optional[date] = Query(None, alias="from", include_in_schema=False),
    to: Optional[date] = Query(None, include_in_schema=False),
) -> Tuple[Optional[date], Optional[date]]:
    """The publication window every funding list takes (a FastAPI dependency): `published_from` /
    `published_to`, with `since`, `until`, `from`, `to` as aliases."""
    return published_from or since or from_, published_to or until or to


def published_sql(where: list, params: dict, window: Tuple[Optional[date], Optional[date]], column: str) -> None:
    """The publication window on `column` (a date or timestamp: the whole last day counts). A handler
    called directly (not through FastAPI) passes None for the dependency."""
    start, end = window or (None, None)
    if start:
        where.append(f"{column} >= :published_from")
        params["published_from"] = start
    if end:
        where.append(f"{column} < CAST(:published_to AS date) + 1")
        params["published_to"] = end


ORDERS = ("recent", "oldest")
ORDERS_DOC = "recent | oldest | updated_asc | updated_desc | created_asc | created_desc"


def standard_order(order: Optional[str], default_sql: str, *, published: str, created: str, updated: str,
                   key: str = "id", amount: Optional[str] = None) -> str:
    """ORDER BY for a funding list: the list's own default when none is asked; recent / oldest on the
    publication date; amount (the largest first) where the list has one; the sync orders on the
    created and change dates."""
    if not order:
        return default_sql
    if order == "amount" and amount:
        return amount
    if order == "recent":
        return f"{published} DESC NULLS LAST, {key} DESC"
    if order == "oldest":
        return f"{published} ASC NULLS LAST, {key} ASC"
    sync = sql_order(order, created, updated, key)
    if sync is None:
        allowed = list(ORDERS) + (["amount"] if amount else []) + list(SYNC_ORDERS)
        raise HTTPException(status_code=400, detail=f"order must be one of {allowed}")
    return sync
