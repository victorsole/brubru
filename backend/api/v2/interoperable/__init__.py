"""/api/v2/interoperable — EU Interoperable (the Interoperable Europe Portal).

The DG DIGIT portal (interoperable-europe.ec.europa.eu) for cross-border
interoperability of public services. It aggregates news, events and reusable
interoperability solutions ACROSS many thematic collections (OSOR, SEMIC, EU
GovTech, EIF/Monitoring, Public Sector Tech Watch, EUPL, CAMSS/EIRA,
Digital-Ready Policymaking, Regulatory Sandboxes, Guidelines, the Academy).

Reads from economy_items (body row in migration 196, body_code='interoperable').
The collection each item belongs to is encoded in its public_url
(/collection/{collection}/news|event|solution/...), so it is filtered at query
time: every feed accepts ?collection=, and /collections/{key} returns one hub's
footprint. 5 mandatory datapoints. Scope: read:economy. Playwright-fed.
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope
from ..economy_endpoints import (EconomyItem, _row_to_item, _LIST_COLS, _DETAIL_COLS,
                                  _ORDERS, _ORDER_SQL)

router = APIRouter(prefix="/interoperable", tags=["v2-interoperable"])
_BODY = "interoperable"
_COLL_LIKE = "public_url ILIKE '%/collection/' || :coll || '/%'"


def _list(db, item_type, *, q, since, until, order, collection, page, limit,
          include_body=False):
    where = ["body_code = :bc", "item_type = :it"]
    params = {"bc": _BODY, "it": item_type, "limit": limit, "offset": (page - 1) * limit}
    if q:
        where.append("search_vector @@ plainto_tsquery('english', :q)"); params["q"] = q
    if since:
        where.append("document_date >= :since"); params["since"] = since
    if until:
        where.append("document_date <= :until"); params["until"] = until
    if collection:
        where.append(_COLL_LIKE); params["coll"] = collection
    clause = " AND ".join(where)
    total = db.execute(text(f"SELECT count(*) FROM economy_items WHERE {clause}"), params).scalar() or 0
    cols = _DETAIL_COLS if include_body else _LIST_COLS
    rows = db.execute(text(f"SELECT {cols} FROM economy_items WHERE {clause} "
                           f"ORDER BY {_ORDER_SQL[order]} LIMIT :limit OFFSET :offset"), params).fetchall()
    return [_row_to_item(r, with_body=include_body) for r in rows], total


def _detail(db, item_type, item_id):
    r = db.execute(text(f"SELECT {_DETAIL_COLS} FROM economy_items "
                        "WHERE id = :id AND body_code = :bc AND item_type = :it"),
                   {"id": item_id, "bc": _BODY, "it": item_type}).fetchone()
    return _row_to_item(r, with_body=True) if r else None


_LIST_DESC = """**What it does**
Lists the Interoperable Europe Portal's {noun}, newest first, drawn from across every thematic collection.

**When to use it**
Track what the EU interoperability community is {verb} without scraping the portal. Filter to one collection with `collection` (e.g. `osor`, `eugovtech`, `semic-support-centre`), or by free text / date.

**Input**
`collection` (a collection slug, e.g. `open-source-observatory-osor`), `q` free-text, `since` / `until` (YYYY-MM-DD), `order` (recent | oldest | title), `page`, `limit` (max 100).

**Try it**
```
GET /api/v2/interoperable/{slug}?collection=eugovtech&limit=10
```

**You get back**
A paginated envelope. Each item carries the 5 datapoints (`public_url`, `document_date`, `creation_date` populated; `body_txt` / `body_html` null on the list by default — pass `include_body=true` to get them in bulk, or use the detail endpoint for one item).

**Data freshness**
Rendered from interoperable-europe.ec.europa.eu with a headless browser, refreshed regularly."""

_DETAIL_DESC = """**What it does**
Returns one Interoperable Europe {noun_singular} in full, including `body_txt` and `body_html`.

**When to use it**
After finding an item id on the list endpoint, fetch the complete record.

**Input**
`item_id` — the Brubru item id from the list endpoint.

**Try it**
```
GET /api/v2/interoperable/{slug}/{{item_id}}
```

**You get back**
A single item with the full 5-datapoint contract populated.

**Data freshness**
Rendered from the item's own page on interoperable-europe.ec.europa.eu."""


def _register(slug, item_type, noun, noun_singular, verb):
    async def list_ep(request: Request, db: Session = Depends(get_db),
                      user: User = Depends(api_user_with_rate_limit),
                      collection: Optional[str] = Query(None, description="Filter to one thematic collection (its slug, e.g. open-source-observatory-osor, eugovtech, semic-support-centre)."),
                      q: Optional[str] = Query(None), since: Optional[date] = Query(None),
                      until: Optional[date] = Query(None), order: str = Query("recent"),
                      page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
                      include_body: bool = Query(False, description="Return `body_txt` / `body_html` on every item in the list. Off by default because bodies dominate the payload, but without it the only route to the text is one detail call PER ITEM, which is not a usable way to ingest a feed.")):
        if order not in _ORDERS:
            raise HTTPException(400, f"order must be one of {sorted(_ORDERS)}")
        items, total = _list(db, item_type, q=q, since=since, until=until, order=order,
                             collection=collection, page=page, limit=limit,
                             include_body=include_body)
        return build_envelope(items, total, page, limit)

    async def detail_ep(request: Request, item_id: int = PathParam(...),
                        db: Session = Depends(get_db), user: User = Depends(api_user_with_rate_limit)):
        item = _detail(db, item_type, item_id)
        if item is None:
            raise HTTPException(404, f"No Interoperable Europe {noun_singular} with id {item_id}")
        return item

    router.add_api_route(f"/{slug}", list_ep, methods=["GET"], response_model=PaginatedResponse[EconomyItem],
                         tags=["v2-interoperable"], summary=f"Interoperable Europe — {noun} (newest first, filter by collection)",
                         description=_LIST_DESC.format(noun=noun, verb=verb, slug=slug))
    router.add_api_route(f"/{slug}/{{item_id}}", detail_ep, methods=["GET"], response_model=EconomyItem,
                         tags=["v2-interoperable"], summary=f"Interoperable Europe — one {noun_singular} (full body)",
                         description=_DETAIL_DESC.format(noun_singular=noun_singular, slug=slug))


# ---- directory ----------------------------------------------------------- #
class _Directory(BaseModel):
    code: str
    name: str
    website: Optional[str] = None
    item_counts: dict = Field(default_factory=dict)
    collections: int = Field(0, description="Number of thematic collections in the directory.")


@router.get("", response_model=_Directory, summary="EU Interoperable folder directory — what it carries",
            description="""**What it does**
Overview of the EU Interoperable folder: stored item counts per resource type and the number of thematic collections.

**When to use it**
A one-call overview before drilling into news, events, solutions or a specific collection.

**Input**
No parameters.

**Try it**
```
GET /api/v2/interoperable
```

**You get back**
The body record (name, website), an `item_counts` map (news / event / solution / collection) and the collections count.

**Data freshness**
Counts are live from the database.""")
async def directory(db: Session = Depends(get_db), user: User = Depends(api_user_with_rate_limit)):
    b = db.execute(text("SELECT code, name, website FROM economy_bodies WHERE code=:c"), {"c": _BODY}).mappings().first()
    counts = {r.item_type: r.n for r in db.execute(
        text("SELECT item_type, count(*) n FROM economy_items WHERE body_code=:c GROUP BY item_type"), {"c": _BODY}).fetchall()}
    if not b:
        raise HTTPException(404, "EU Interoperable body not registered")
    return _Directory(code=b["code"], name=b["name"], website=b["website"],
                      item_counts=counts, collections=counts.get("collection", 0))


# ---- news / events / solutions ------------------------------------------- #
_register("news", "news", "news", "news item", "publishing")
_register("events", "event", "events", "event", "hosting")
_register("solutions", "solution", "reusable solutions", "solution", "sharing")


# ---- collections directory + per-collection footprint -------------------- #
@router.get("/collections", response_model=PaginatedResponse[EconomyItem],
            summary="Interoperable Europe — the thematic collections directory",
            description="""**What it does**
Lists the portal's thematic collections (OSOR, SEMIC, EU GovTech, EIF/Monitoring, Public Sector Tech Watch, EUPL, CAMSS/EIRA, Digital-Ready Policymaking, Regulatory Sandboxes, Guidelines, the Academy), each a snapshot with its standing description.

**When to use it**
To discover the hubs you can then filter on (`?collection=`) or open with the per-collection endpoint.

**Input**
`q` free-text, `order`, `page`, `limit`.

**Try it**
```
GET /api/v2/interoperable/collections
```

**You get back**
A paginated envelope of collection snapshots, each with the 5 datapoints (`public_url` is the hub's page; pass `include_body=true` for the full description, or use the per-collection endpoint).

**Data freshness**
Rendered from the portal, refreshed regularly.""")
async def list_collections(request: Request, db: Session = Depends(get_db),
                           user: User = Depends(api_user_with_rate_limit),
                           q: Optional[str] = Query(None), order: str = Query("title"),
                           page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=100),
                           include_body: bool = Query(False, description="Return `body_txt` / `body_html` on every item in the list. Off by default because bodies dominate the payload, but without it the only route to the text is one detail call PER ITEM, which is not a usable way to ingest a feed.")):
    if order not in _ORDERS:
        raise HTTPException(400, f"order must be one of {sorted(_ORDERS)}")
    items, total = _list(db, "collection", q=q, since=None, until=None, order=order,
                         collection=None, page=page, limit=limit,
                         include_body=include_body)
    return build_envelope(items, total, page, limit)


class _CollectionFootprint(BaseModel):
    collection_key: str
    collection: Optional[EconomyItem] = Field(None, description="The collection snapshot (full description).")
    recent_news: List[EconomyItem] = Field(default_factory=list)
    recent_events: List[EconomyItem] = Field(default_factory=list)
    recent_solutions: List[EconomyItem] = Field(default_factory=list)


@router.get("/collections/{collection_key}", response_model=_CollectionFootprint,
            summary="Interoperable Europe — one collection's footprint (description + its recent items)",
            description="""**What it does**
Returns one thematic collection's snapshot plus its most recent news, events and reusable solutions.

**When to use it**
'Show me everything in OSOR / EU GovTech / SEMIC' in one call.

**Input**
`collection_key` (path; the collection slug, e.g. `open-source-observatory-osor`, `eugovtech`, `semic-support-centre`), `limit` (items per resource, max 50).

**Try it**
```
GET /api/v2/interoperable/collections/open-source-observatory-osor
```

**You get back**
`{collection_key, collection, recent_news, recent_events, recent_solutions}` — the collection snapshot (full body) and lists of its recent items, each with the 5 datapoints.

**Data freshness**
Rendered from the portal, refreshed regularly.""")
async def collection_footprint(collection_key: str = PathParam(..., description="Collection slug."),
                               limit: int = Query(15, ge=1, le=50),
                               include_body: bool = Query(False, description="Return `body_txt` / `body_html` on every item in the list. Off by default because bodies dominate the payload, but without it the only route to the text is one detail call PER ITEM, which is not a usable way to ingest a feed."),
                               db: Session = Depends(get_db), user: User = Depends(api_user_with_rate_limit)):
    # Accepts the `id` the /collections list publishes as well as the slug.
    # This resource's key lives only inside public_url -- there is no
    # collection_key column -- so before 31 Aug 2026 a client following `id`
    # from the collection had no way in at all.
    snap = None
    if str(collection_key).isdigit():
        snap = db.execute(text(f"SELECT {_DETAIL_COLS} FROM economy_items "
                               "WHERE id = :i AND body_code = :bc AND item_type = 'collection'"),
                          {"i": int(collection_key), "bc": _BODY}).fetchone()
    if snap is None:
        snap = db.execute(text(f"SELECT {_DETAIL_COLS} FROM economy_items "
                               "WHERE body_code=:bc AND item_type='collection' AND public_url ILIKE '%/collection/' || :k"),
                          {"bc": _BODY, "k": collection_key}).fetchone()
    # The slug is what filters the member items, so recover it from the snapshot
    # when the caller arrived by id.
    if snap is not None and str(collection_key).isdigit():
        url = (dict(snap._mapping).get("public_url") or "")
        if "/collection/" in url:
            collection_key = url.rsplit("/collection/", 1)[-1].strip("/")
    def recent(itype):
        cols = _DETAIL_COLS if include_body else _LIST_COLS
        rows = db.execute(text(f"SELECT {cols} FROM economy_items "
                               f"WHERE body_code=:bc AND item_type=:it AND {_COLL_LIKE} "
                               "ORDER BY document_date DESC NULLS LAST, id DESC LIMIT :lim"),
                          {"bc": _BODY, "it": itype, "coll": collection_key, "lim": limit}).fetchall()
        return [_row_to_item(r, with_body=include_body) for r in rows]
    news, events, sols = recent("news"), recent("event"), recent("solution")
    if snap is None and not (news or events or sols):
        raise HTTPException(404, f"No Interoperable Europe collection or content for '{collection_key}'")
    return _CollectionFootprint(
        collection_key=collection_key,
        collection=_row_to_item(snap, with_body=True) if snap else None,
        recent_news=news, recent_events=events, recent_solutions=sols)
