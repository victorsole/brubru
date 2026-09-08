"""
Shared models + resource-registration helper for the economy & finance v2 folders
(ECB, the EU financial institutions, ESM). All resources read from economy_items
(migration 119) and expose the 5 mandatory datapoints.

List endpoints return metadata + the datapoint contract with bodies nulled
(cheap); detail endpoints return the full body_txt / body_html.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import Depends, HTTPException, Path as PathParam, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope

_ORDERS = {"recent", "oldest", "title"}
# coalesce(document_date, creation_date), not bare document_date, in BOTH the filter
# (`_list_items`) and the sort. Measured 8 September 2026: 1,761 news rows across 17
# bodies carry no document_date because the upstream feed published none, and a bare
# `document_date >= :since` is NULL for those rows, so every dated window on all ~332
# factory-generated endpoints dropped them entirely. `creation_date` (when Brubru
# ingested the row) is a fact we actually know. It is deliberately NOT written into
# document_date: inventing a publication date we were never given is what
# feedback_backfill_no_hallucination forbids, and the payload still returns
# document_date as NULL so the caller can see the date is unknown.
_DATE_SORT = "coalesce(document_date, creation_date)"
_ORDER_SQL = {
    "recent": f"{_DATE_SORT} DESC NULLS LAST, id DESC",
    "oldest": f"{_DATE_SORT} ASC NULLS LAST, id ASC",
    "title": "title ASC, id ASC",
}


class _DataPoints(BaseModel):
    """The 5 mandatory Brubru datapoints — present even when null."""
    public_url: Optional[str] = Field(None, description="Canonical URL of the item on the institution's own website.")
    body_txt: Optional[str] = Field(None, description="Plain-text body (full on detail endpoints; null on list).")
    body_html: Optional[str] = Field(None, description="HTML body (full on detail endpoints; null on list).")
    document_date: Optional[datetime] = Field(None, description="The item's own published date.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested the item.")


class EconomyItem(_DataPoints):
    id: int = Field(..., description="Stable Brubru item id (use it on the detail endpoint).")
    body_code: str = Field(..., description="Body code: 'ecb' or 'ecb_ssm'.")
    item_type: str = Field(..., description="news | publication | event | legal.")
    title: str
    summary: Optional[str] = None
    source_kind: Optional[str] = Field(None, description="How the item was ingested: rss | html | pdf | cellar.")


def _row_to_item(r, *, with_body: bool) -> EconomyItem:
    return EconomyItem(
        id=r.id, body_code=r.body_code, item_type=r.item_type, title=r.title,
        summary=r.summary, source_kind=r.source_kind,
        public_url=r.public_url,
        body_txt=(r.body_txt if with_body else None),
        body_html=(r.body_html if with_body else None),
        document_date=r.document_date, creation_date=r.creation_date,
    )


_LIST_COLS = "id, body_code, item_type, title, summary, public_url, document_date, creation_date, source_kind"
_DETAIL_COLS = "id, body_code, item_type, title, summary, public_url, body_txt, body_html, document_date, creation_date, source_kind"


def _list_items(db: Session, body_code: str, item_type: str, q, since, until, order,
                page, limit, include_body: bool = False):
    where = ["body_code = :bc", "item_type = :it"]
    params = {"bc": body_code, "it": item_type, "limit": limit, "offset": (page - 1) * limit}
    if q:
        where.append("search_vector @@ plainto_tsquery('english', :q)")
        params["q"] = q
    if since:
        where.append(f"{_DATE_SORT} >= :since")
        params["since"] = since
    if until:
        where.append(f"{_DATE_SORT} <= :until")
        params["until"] = until
    clause = " AND ".join(where)
    total = db.execute(text(f"SELECT count(*) FROM economy_items WHERE {clause}"), params).scalar() or 0
    # Select the body columns only when asked: they dominate the row size, and
    # the default list is meant to stay cheap.
    cols = _DETAIL_COLS if include_body else _LIST_COLS
    rows = db.execute(
        text(f"SELECT {cols} FROM economy_items WHERE {clause} "
             f"ORDER BY {_ORDER_SQL[order]} LIMIT :limit OFFSET :offset"), params
    ).fetchall()
    return [_row_to_item(r, with_body=include_body) for r in rows], total


def _get_item(db: Session, body_code: str, item_type: str, item_id: int):
    r = db.execute(
        text(f"SELECT {_DETAIL_COLS} FROM economy_items "
             "WHERE id = :id AND body_code = :bc AND item_type = :it"),
        {"id": item_id, "bc": body_code, "it": item_type},
    ).fetchone()
    return _row_to_item(r, with_body=True) if r else None


_DESC_LIST = """**What it does**
Lists {body}'s {noun}, newest first. {extra}

**When to use it**
Track what {acro} is publishing without scraping its website. Filter by free text or date, page through the archive, then call the detail endpoint for an item's full body.

**Input**
`q` free-text search, `since` / `until` (YYYY-MM-DD) on the item date, `order` (recent | oldest | title), `page`, `limit` (max 100).

**Try it**
```
GET {path}?order=recent&limit=10
```

**You get back**
A paginated envelope of items. Each carries the 5 datapoints. `body_txt` / `body_html` are null on the list by default — **pass `include_body=true` to get them in bulk**, or call the detail endpoint for a single item.

**Data freshness**
Refreshed from {source}."""

_DESC_DETAIL = """**What it does**
Returns one {body} {noun_singular} in full, including `body_txt` and `body_html`.

**When to use it**
After finding an item id on the list endpoint, fetch the complete record (full body + all 5 datapoints).

**Input**
`item_id` — the Brubru item id from the list endpoint.

**Try it**
```
GET {path}/{{item_id}}
```

**You get back**
A single item with the full 5-datapoint contract populated.

**Data freshness**
Refreshed from {source}."""


def register_resource(router, *, body_code, item_type, slug, noun, body_name, acronym,
                      source, tag, extra=""):
    """Add list + detail GET routes for one (body, resource) onto `router`."""
    noun_singular = noun.rstrip("s") if noun.endswith("s") else noun
    path_hint = slug if slug.startswith("/") else f"/{slug}"

    async def list_ep(
        request: Request,
        db: Session = Depends(get_db),
        user: User = Depends(api_user_with_rate_limit),
        q: Optional[str] = Query(None, description="Free-text search over title, summary and body."),
        since: Optional[date] = Query(None, description="Only items on/after this date (YYYY-MM-DD). `from` is accepted as an alias."),
        until: Optional[date] = Query(None, description="Only items on/before this date (YYYY-MM-DD). `to` is accepted as an alias."),
        # v2 is split on the date-window vocabulary: 332 operations take
        # `since`/`until` and the four cross-body aggregators (/news/all,
        # /events/all, /consultations/all) take `from`/`to`. FastAPI drops an
        # unknown query param SILENTLY with HTTP 200, so a caller who learned one
        # spelling gets the UNFILTERED corpus from the other family and no error:
        # measured 8 September 2026, /api/v2/news/all?since=..&until=.. returned
        # 14,720 rows where from=..&to=.. returned 152. Accepting both names
        # everywhere removes the whole failure class and breaks no existing caller.
        from_: Optional[date] = Query(None, alias="from", include_in_schema=False),
        to: Optional[date] = Query(None, include_in_schema=False),
        order: str = Query("recent", description="recent | oldest | title."),
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        include_body: bool = Query(
            False,
            description=(
                "Return `body_txt` / `body_html` on every item in the list. Off by "
                "default because bodies dominate the payload, but without it the "
                "only route to the text is one detail call PER ITEM, which is not "
                "a usable way to ingest a feed."
            ),
        ),
    ):
        if order not in _ORDERS:
            raise HTTPException(status_code=400, detail=f"order must be one of {sorted(_ORDERS)}")
        since = since or from_
        until = until or to
        items, total = _list_items(db, body_code, item_type, q, since, until, order,
                                   page, limit, include_body=include_body)
        return build_envelope(items, total, page, limit)

    async def detail_ep(
        request: Request,
        item_id: int = PathParam(..., description="Brubru item id from the list endpoint."),
        db: Session = Depends(get_db),
        user: User = Depends(api_user_with_rate_limit),
    ):
        item = _get_item(db, body_code, item_type, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"No {body_name} {noun_singular} with id {item_id}")
        return item

    router.add_api_route(
        path_hint, list_ep, methods=["GET"],
        response_model=PaginatedResponse[EconomyItem], tags=[tag],
        summary=f"{body_name} — {noun} (newest first)",
        description=_DESC_LIST.format(body=body_name, noun=noun, acro=acronym, path=path_hint,
                                      source=source, extra=extra),
    )
    router.add_api_route(
        f"{path_hint}/{{item_id}}", detail_ep, methods=["GET"],
        response_model=EconomyItem, tags=[tag],
        summary=f"{body_name} — one {noun_singular} (full body)",
        description=_DESC_DETAIL.format(body=body_name, noun_singular=noun_singular, path=path_hint,
                                        source=source),
    )


# ---------------------------------------------------------------------------
# Single-body own-folder factory — used by the single-market / digital agencies
# (BEREC, ACER, EIT, ENISA, eu-LISA, EUIPO, CPVO). Each is one body in its own
# folder, so its resources sit directly under the folder prefix plus a small
# directory endpoint. Mirrors the hand-written ESM folder.
# ---------------------------------------------------------------------------
def make_single_body_folder(*, body_code, prefix, body_name, acronym, tag, resources):
    """Return an APIRouter for a single-body own-folder.

    resources: list of dicts with keys item_type, slug, noun, source, extra.
    """
    from fastapi import APIRouter
    from typing import List, Optional
    from pydantic import BaseModel as _BM, Field as _F

    router = APIRouter(prefix=prefix, tags=[tag])

    class _AgencyBody(_BM):
        code: str
        acronym: str
        name: str
        mandate: Optional[str] = None
        website: Optional[str] = None
        item_counts: dict = _F(default_factory=dict)

    async def _directory(
        request: Request,
        db: Session = Depends(get_db),
        user: User = Depends(api_user_with_rate_limit),
    ):
        bodies = db.execute(
            text("SELECT code, acronym, name, mandate, website FROM economy_bodies WHERE code = :c"),
            {"c": body_code},
        ).fetchall()
        counts = db.execute(
            text("SELECT item_type, count(*) AS n FROM economy_items WHERE body_code = :c GROUP BY item_type"),
            {"c": body_code},
        ).fetchall()
        cmap = {c.item_type: c.n for c in counts}
        return [_AgencyBody(code=b.code, acronym=b.acronym, name=b.name, mandate=b.mandate,
                            website=b.website, item_counts=cmap) for b in bodies]

    router.add_api_route(
        "", _directory, methods=["GET"], response_model=List[_AgencyBody], tags=[tag],
        summary=f"{acronym} folder directory — what {acronym} carries",
        description=(
            f"**What it does**\nReturns {body_name} ({acronym}) with a count of stored items per "
            f"resource type.\n\n**When to use it**\nA one-call overview before drilling into a "
            f"specific feed.\n\n**Input**\nNo parameters.\n\n**Try it**\n```\nGET /api/v2{prefix}\n```\n\n"
            f"**You get back**\nOne body record with acronym, name, mandate, website and an "
            f"`item_counts` map.\n\n**Data freshness**\nCounts are live from the database."
        ),
    )
    for r in resources:
        register_resource(
            router, body_code=body_code, item_type=r["item_type"], slug=r["slug"],
            noun=r["noun"], body_name=body_name, acronym=acronym, tag=tag,
            source=r["source"], extra=r.get("extra", ""),
        )
    return router
