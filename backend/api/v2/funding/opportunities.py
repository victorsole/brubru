"""GET /api/v2/funding/opportunities: every call and tender Brubru holds, each procedure once.

Funding standard Phase 3b (proposal of 23 Oct 2026 §6; Victor's decisions of 29 Oct 2026). One list
over TED (`tenders`), the F&T Portal's calls for tenders, calls for proposals and calls in cascade,
and the agencies' own tenders, grants and calls for expression of interest (`economy_items`).

A procedure stored twice is served once, matched on exact keys only (O104, measured 29 Oct 2026):
  a TED notice re-listed on the portal under its TED number (386)      -> the TED row
  an F&T tender copied into the TED table for the Tenderator (306)      -> the F&T row
  an agency's page that links to an F&T tender Brubru holds (81)        -> the F&T row
  an agency's grant that is an F&T topic (38: Innovation Fund, Justice) -> the F&T row
Each served item lists its copies' items in `same_as`. Not matched yet: TED notices whose
ContractFolderID is an F&T tender id (212 on 29 Oct): that id is not stored.

How a page is made: a light UNION of every source's key columns is filtered, counted, ordered and
paged in SQL; then each row of the page is built by its own list's builder, so an item here is the
same item, field for field, as on its own list, and `self` opens it there.
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Numeric, String, and_, cast, column, func, literal, literal_column, null, select, table, text, union_all
from sqlalchemy.orm import Session

from api.v1 import funding_tenders_collections as ft
from api.v1 import w5_endpoints as ted
from api.v1._change_window import SYNC_ORDERS, UpperBoundDatetime, validate_window
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse
from api.v1._pagination import stable
from api.v1._search import text_match
from core.database import get_db
from models.funding_tenders import FtCallForProposals, FtCallForTenders
from models.tender import Tender
from models.user import User
from services.funding.shared_fields import AMOUNT_EUR_RULE, page_amounts_eur, with_body_names
from ..economy_endpoints import (FUNDING_LISTS, _DETAIL_COLS, _PROCUREMENT_COLS, _as_funding, _row_to_item,
                                 build_envelope)
from . import ft_cascade_calls as cascade
from ._standard import amount_range, include_body_param, without_bodies
from .funding_all import _item_routes

router = APIRouter()

_AGENCY_TYPES = ("tender", "grant", "eoi_call", "startup_funding")
ITEM_TYPES = ("tender", "grant", "cascade_call", "eoi_call", "startup_funding")
_ITEM_PATHS = {"ted": "/api/v2/funding/tenders/{}", "ft_tender": "/api/v2/funding/ft-calls-for-tenders/{}",
               "ft_call": "/api/v2/funding/ft-calls-for-proposals/{}", "cascade": "/api/v2/funding/ft-cascade-calls/{}"}

_t = table("tenders", *map(column, (
    "id", "publication_number", "title", "description", "summary", "official_name", "publication_date",
    "created_at", "updated_at", "submission_deadline", "status", "estimated_value", "estimated_value_currency",
    "buyer_country", "source")))
_f = table("ft_calls_for_tenders", *map(column, (
    "id", "tender_reference", "title", "description", "contracting_authority", "published_at", "first_seen_at",
    "content_updated_at", "deadline", "status", "estimated_value", "value_currency", "source_url", "is_test")))
_c = table("ft_calls_for_proposals", *map(column, (
    "id", "topic_id", "title", "description", "published_at", "first_seen_at", "content_updated_at", "deadline",
    "status", "indicative_budget", "budget_currency", "framework_programme", "is_test")))
_k = table("ft_cascade_calls", *map(column, (
    "id", "title", "description", "published_at", "first_seen", "last_updated", "deadline", "status",
    "indicative_budget", "budget_currency", "is_test")))
_e = table("economy_items", *map(column, (
    "id", "body_code", "item_type", "title", "summary", "body_txt", "public_url", "document_date",
    "creation_date", "updated_at", "deadline", "status")))

# Each source without the copies another source serves (O104), matched on an exact key.
_TED_NOT_FT_COPY = text(
    "NOT (coalesce(tenders.source, '') = 'ft_portal' AND EXISTS (SELECT 1 FROM ft_calls_for_tenders x "
    "WHERE NOT x.is_test AND 'FT-' || x.tender_reference = tenders.publication_number))")
_FT_NOT_TED_NOTICE = text(
    "NOT (ft_calls_for_tenders.source_url LIKE '%ted.europa.eu%' AND EXISTS (SELECT 1 FROM tenders x "
    "WHERE x.publication_number = ft_calls_for_tenders.tender_reference))")
_AGENCY_FT_TENDER = "substring(economy_items.public_url from '/tender-details/([^/?#]+)$')"
_AGENCY_FT_TOPIC = "upper(substring(economy_items.public_url from '/topic-details/([^/?#]+)$'))"
_AGENCY_NOT_FT_COPY = text(
    f"NOT EXISTS (SELECT 1 FROM ft_calls_for_tenders x WHERE NOT x.is_test AND x.tender_reference = {_AGENCY_FT_TENDER}) "
    f"AND NOT EXISTS (SELECT 1 FROM ft_calls_for_proposals x WHERE NOT x.is_test AND upper(x.topic_id) = {_AGENCY_FT_TOPIC})")


def _utc(col):
    """A naive UTC timestamp (the F&T tables) as a timestamptz, so every side of the union compares alike."""
    return func.timezone("UTC", col)


def _sources(q: Optional[str], programme: Optional[str]):
    """One SELECT per source with the union's columns; q is matched on each source's own text columns."""
    cols = ("src", "rid", "item_type", "body_code", "title", "document_date", "creation_date", "updated_date",
            "deadline", "status", "amount_eur", "country", "programme")

    def side(src, rid, item_type, body_code, tbl, doc, created, updated, deadline, status, amount, country,
             programme_col, text_cols, *where):
        s = select(literal(src).label("src"), cast(rid, String).label("rid"), item_type.label("item_type"),
                   body_code.label("body_code"), tbl.c.title.label("title"), doc.label("document_date"),
                   created.label("creation_date"), updated.label("updated_date"), deadline.label("deadline"),
                   status.label("status"), amount.label("amount_eur"), country.label("country"),
                   programme_col.label("programme")).select_from(tbl)
        cond = text_match(q, *text_cols)
        return s.where(*where, *([cond] if cond is not None else []))

    sides = [
        side("ted", _t.c.id, literal("tender"), cast(null(), String), _t, _t.c.publication_date, _t.c.created_at,
             _t.c.updated_at, _t.c.submission_deadline, _t.c.status, literal_column(ted._TED_EUR), _t.c.buyer_country,
             cast(null(), String), (_t.c.title, _t.c.description, _t.c.summary, _t.c.official_name),
             _TED_NOT_FT_COPY),
        side("ft_tender", _f.c.id, literal("tender"), literal("ftportal"), _f, _utc(_f.c.published_at),
             _f.c.first_seen_at, _f.c.content_updated_at, _utc(_f.c.deadline), _f.c.status,
             literal_column(ft._FT_TENDER_EUR), cast(null(), String), cast(null(), String),
             (_f.c.title, _f.c.description, _f.c.contracting_authority), ~_f.c.is_test, _FT_NOT_TED_NOTICE),
        side("ft_call", _c.c.id, literal("grant"), literal("ftportal"), _c, _utc(_c.c.published_at),
             _c.c.first_seen_at, _c.c.content_updated_at, _utc(_c.c.deadline), _c.c.status,
             literal_column(ft._CALL_EUR), cast(null(), String), _c.c.framework_programme,
             (_c.c.title, _c.c.description), ~_c.c.is_test),
        side("cascade", _k.c.id, literal("cascade_call"), literal("ftportal"), _k, _k.c.published_at,
             _k.c.first_seen, _k.c.last_updated, _k.c.deadline, _k.c.status, literal_column(cascade._CASCADE_EUR),
             cast(null(), String), cast(null(), String), (_k.c.title, _k.c.description), ~_k.c.is_test),
        # The agency lists date an item by its document_date, else when Brubru first saw it (economy_endpoints).
        side("agency", _e.c.id, _e.c.item_type, _e.c.body_code, _e, func.coalesce(_e.c.document_date, _e.c.creation_date),
             _e.c.creation_date, _e.c.updated_at, _e.c.deadline, _e.c.status, cast(null(), Numeric), cast(null(), String),
             cast(null(), String), (_e.c.title, _e.c.summary, _e.c.body_txt),
             _e.c.item_type.in_(_AGENCY_TYPES), _AGENCY_NOT_FT_COPY),
    ]
    u = union_all(*sides).subquery("opp")
    assert tuple(u.c.keys()) == cols
    return u


_ORDERS = ("recent", "oldest", "deadline", "amount")


def _order_by(u, order: str):
    """The order's own columns; `_tiebreak` completes it (src + rid is unique across the union)."""
    if order in SYNC_ORDERS:
        col = u.c.updated_date if order.startswith("updated") else u.c.creation_date
        return (col.asc() if order.endswith("_asc") else col.desc(),)
    return {
        "recent": (u.c.document_date.desc().nullslast(),),
        "oldest": (u.c.document_date.asc().nullslast(),),
        "deadline": (u.c.deadline.asc().nullslast(),),
        "amount": (u.c.amount_eur.desc().nullslast(),),
    }[order]


def _tiebreak(u, order: str):
    """The unique key, in the order's direction, so OFFSET pages never overlap (stable())."""
    down = order in ("recent", "amount") or order.endswith("_desc")
    return (u.c.src.desc(), u.c.rid.desc()) if down else (u.c.src.asc(), u.c.rid.asc())


class OpportunityItem(BaseModel):
    """A call or tender as its own list serves it, plus `self` (that list's item) and `same_as`."""
    model_config = ConfigDict(extra="allow")
    id: Any = Field(..., description="The item's id on its own list (`self`): an integer for TED, cascade and agency items, a UUID for F&T Portal tenders and calls.")
    self: Optional[str] = Field(None, description="This item on its own list (TED /tenders, /ft-calls-for-tenders, /ft-calls-for-proposals, /ft-cascade-calls or an agency's list).")
    item_type: str = Field(..., description="tender | grant | cascade_call | eoi_call | startup_funding.")
    title: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[str] = Field(None, description="forthcoming | open | closed | cancelled | unknown.")
    body_code: Optional[str] = Field(None, description="ftportal for the F&T Portal's items, the agency's code for its own, null for TED (buyers across Europe).")
    body_name: Optional[str] = None
    amount_eur: Optional[float] = Field(None, description=f"The item's main figure in euros: {AMOUNT_EUR_RULE}.")
    public_url: Optional[str] = None
    # A date or a datetime, as the item's own list serves it (a call's document_date is a day).
    document_date: Union[datetime, date, None] = None
    creation_date: Union[datetime, date, None] = None
    updated_date: Union[datetime, date, None] = None
    deadline: Union[datetime, date, None] = None
    body_txt: Optional[str] = None
    body_html: Optional[str] = None
    same_as: List[str] = Field(default_factory=list, description="The other lists' items for this same procedure (their `self`): a TED notice the portal re-lists, the portal tender copied into TED for the Tenderator, an agency's page for it. Empty when Brubru holds it once.")


def _build(db: Session, rows, include_body: bool, base: str, routes: dict) -> List[dict]:
    """Each page row built by its own list's builder, in the page's order."""
    ids: Dict[str, list] = {}
    for r in rows:
        ids.setdefault(r.src, []).append(r.rid)
    built: Dict[tuple, Any] = {}
    if ids.get("ted"):
        recs = db.query(Tender).options(*ted.ted_list_deferred()).filter(Tender.id.in_([int(i) for i in ids["ted"]])).all()
        converted = page_amounts_eur(db, recs, **ted._TED_AMOUNT)
        built.update({("ted", str(r.id)): ted.tender_item(r, converted) for r in recs})
    if ids.get("ft_tender"):
        recs = db.query(FtCallForTenders).filter(FtCallForTenders.id.in_(ids["ft_tender"])).all()
        converted = page_amounts_eur(db, recs, **ft._FT_TENDER_AMOUNT)
        built.update({("ft_tender", str(r.id)): ft._tender_to_item(r, converted=converted) for r in recs})
    if ids.get("ft_call"):
        recs = db.query(FtCallForProposals).filter(FtCallForProposals.id.in_(ids["ft_call"])).all()
        built.update({("ft_call", str(r.id)): ft._proposal_to_item(r) for r in recs})
    if ids.get("cascade"):
        recs = db.execute(text(f"SELECT {cascade._COLS}{cascade._BODY} FROM ft_cascade_calls WHERE id = ANY(:ids)"),
                          {"ids": [int(i) for i in ids["cascade"]]}).mappings().all()
        built.update({("cascade", str(r["id"])): cascade._item(r, with_body=True) for r in recs})
    if ids.get("agency"):
        recs = db.execute(text(f"SELECT {_DETAIL_COLS}{_PROCUREMENT_COLS}, status FROM economy_items WHERE id = ANY(:ids)"),
                          {"ids": [int(i) for i in ids["agency"]]}).fetchall()
        for r in recs:
            how = FUNDING_LISTS.get((r.body_code, r.item_type), {"procurement": True, "reference_name": None})
            item = _row_to_item(r, with_body=True, procurement=how["procurement"])
            built[("agency", str(r.id))] = _as_funding(db, [item], how["procurement"], how["reference_name"])[0]
    with_body_names(db, [i for i in built.values()])
    same = _same_as(db, rows, base, routes)
    out = []
    for r in rows:
        item = built.get((r.src, r.rid))
        if item is None:      # removed between the page query and the build
            continue
        d = item.model_dump()
        if r.src == "agency":
            path = routes.get((d.get("body_code"), d.get("item_type")))
            d["self"] = base + path.replace("{item_id}", str(d["id"])) if path else None
        else:
            d["self"] = base + _ITEM_PATHS[r.src].format(d["id"])
        d["same_as"] = same.get((r.src, r.rid), [])
        if not include_body:
            d["body_txt"] = d["body_html"] = None
        out.append(d)
    return out


def _same_as(db: Session, rows, base: str, routes: dict) -> Dict[tuple, List[str]]:
    """The copies of the page's items, by the keys that folded them in (one query per kind)."""
    out: Dict[tuple, List[str]] = {}
    ted_ids = [int(r.rid) for r in rows if r.src == "ted"]
    ft_ids = [r.rid for r in rows if r.src == "ft_tender"]
    call_ids = [r.rid for r in rows if r.src == "ft_call"]
    if ted_ids:
        for tid, fid in db.execute(text(
                "SELECT t.id, x.id FROM tenders t JOIN ft_calls_for_tenders x ON x.tender_reference = t.publication_number "
                "AND x.source_url LIKE '%ted.europa.eu%' WHERE t.id = ANY(:ids)"), {"ids": ted_ids}).fetchall():
            out.setdefault(("ted", str(tid)), []).append(base + _ITEM_PATHS["ft_tender"].format(fid))
    if ft_ids:
        for fid, tid in db.execute(text(
                "SELECT x.id, t.id FROM ft_calls_for_tenders x JOIN tenders t ON t.publication_number = 'FT-' || x.tender_reference "
                "AND t.source = 'ft_portal' WHERE x.id = ANY(CAST(:ids AS uuid[]))"), {"ids": ft_ids}).fetchall():
            out.setdefault(("ft_tender", str(fid)), []).append(base + _ITEM_PATHS["ted"].format(tid))
    for src, ids, sql in (
            ("ft_tender", ft_ids, "SELECT x.id, economy_items.id, economy_items.body_code, economy_items.item_type "
                                  f"FROM ft_calls_for_tenders x JOIN economy_items ON {_AGENCY_FT_TENDER} = x.tender_reference "
                                  "AND economy_items.item_type = ANY(:types) WHERE x.id = ANY(CAST(:ids AS uuid[]))"),
            ("ft_call", call_ids, "SELECT x.id, economy_items.id, economy_items.body_code, economy_items.item_type "
                                  f"FROM ft_calls_for_proposals x JOIN economy_items ON {_AGENCY_FT_TOPIC} = upper(x.topic_id) "
                                  "AND economy_items.item_type = ANY(:types) WHERE x.id = ANY(CAST(:ids AS uuid[]))")):
        if not ids:
            continue
        # item_type first: the funding rows of economy_items are a few thousand of its news, events and files
        for xid, eid, body_code, item_type in db.execute(text(sql), {"ids": ids, "types": list(_AGENCY_TYPES)}).fetchall():
            path = routes.get((body_code, item_type))
            if path:
                out.setdefault((src, str(xid)), []).append(base + path.replace("{item_id}", str(eid)))
    return out


_DESC = """**What it does**
Every call and tender Brubru holds, in one list, **each procedure once**: TED notices (`/tenders`), the EU Funding & Tenders Portal's calls for tenders, calls for proposals and calls for funding in cascade, and the EU agencies' own tenders, grants and calls for expression of interest.

**When to use it**
"What can I bid for or apply to?" across every source at once, for example every open call or tender on a subject: `status=open&q=hydrogen`. To work with one source and its own fields, use its list; each item's `self` opens it there.

**Input**
`q` (words in the title or text; accents ignored), `status` (forthcoming | open | closed | cancelled | unknown), `item_type` (tender | grant | cascade_call | eoi_call | startup_funding), `body` (`ftportal` for the portal's items, an agency's code such as `efsa`), `country` (a TED buyer's two-letter country; the other items name none), `programme` (words in a call's programme), `deadline_from`/`deadline_to`, `published_from`/`published_to` (the item's `document_date`; `since`, `until`, `from`, `to` are aliases), `created_from`/`created_to` and `updated_from`/`updated_to` (incremental sync; a bare date as `_to` covers the whole day), `min_amount_eur`/`max_amount_eur`, `order` (recent | oldest | deadline | amount | updated_asc | updated_desc | created_asc | created_desc), `page`, `limit` (default 50, max 200), `include_body` (default true).

**Try it**
```
GET /api/v2/funding/opportunities?status=open&q=hydrogen
GET /api/v2/funding/opportunities?item_type=grant&deadline_from=2026-11-01
GET /api/v2/funding/opportunities?updated_from=2026-10-29&order=updated_asc
```

**You get back**
A paginated list. Each item is the item of its own list, field for field (a TED notice carries the TED fields, a call its topic and programme), with `self` (that list's item) and `same_as`: the other lists' items for the same procedure. A procedure Brubru stores twice is served once: a TED notice the portal re-lists under its TED number is the TED item; a portal tender (copied into the TED table for the Tenderator) and an agency's page that links to a portal tender or topic are the portal's item. Two copies Brubru cannot yet match on an exact key are both served: a TED notice and a portal tender that share only the procedure's internal id.

**Data freshness**
As each source: TED and the F&T Portal daily; the agencies' pages as they are re-read. The F&T Portal's calls and tenders are complete from those that started on 1 January 2021 (the closed ones read back from the portal on 29 October 2026); earlier ones are held only where Brubru read them while they were open. TED notices are those `/tenders` holds."""


@router.get("/opportunities", response_model=PaginatedResponse[OpportunityItem], tags=["v2-funding"],
            summary="Every call and tender, each procedure once: TED, the F&T Portal and the EU agencies",
            description=_DESC)
async def list_opportunities(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
    q: Optional[str] = Query(None, description="Words in the title or text (accents ignored; a short word matches whole words)."),
    status: Optional[str] = Query(None, description="forthcoming | open | closed | cancelled | unknown."),
    item_type: Optional[str] = Query(None, description="tender | grant | cascade_call | eoi_call | startup_funding."),
    body: Optional[str] = Query(None, description="ftportal (the F&T Portal's items) or an agency's code, e.g. efsa, eea."),
    country: Optional[str] = Query(None, description="A TED buyer's country, two letters (ISO 3166-1), e.g. BE. The portal's and the agencies' items name no country, so they are left out."),
    programme: Optional[str] = Query(None, description="Words in a call's programme, e.g. Horizon Europe. Only calls for proposals name one."),
    deadline_from: Optional[date] = Query(None, description="Deadline on or after (YYYY-MM-DD)."),
    deadline_to: Optional[date] = Query(None, description="Deadline on or before (YYYY-MM-DD)."),
    published_from: Optional[date] = Query(None, description="The item's date (`document_date`) on or after (YYYY-MM-DD); `since` and `from` are aliases."),
    published_to: Optional[date] = Query(None, description="The item's date (`document_date`) on or before (YYYY-MM-DD); `until` and `to` are aliases."),
    since: Optional[date] = Query(None, description="The same as `published_from`."),
    until: Optional[date] = Query(None, description="The same as `published_to`."),
    from_: Optional[date] = Query(None, alias="from", include_in_schema=False),
    to: Optional[date] = Query(None, include_in_schema=False),
    created_from: Optional[datetime] = Query(None, description="First recorded by Brubru on or after (ISO date or datetime, UTC)."),
    created_to: Optional[UpperBoundDatetime] = Query(None, description="First recorded by Brubru on or before; a bare date covers the whole day."),
    updated_from: Optional[datetime] = Query(None, description="Content last changed on or after (ISO date or datetime, UTC). The incremental-sync filter."),
    updated_to: Optional[UpperBoundDatetime] = Query(None, description="Content last changed on or before; a bare date covers the whole day."),
    order: str = Query("recent", description="recent (the newest first) | oldest | deadline (the nearest first) | amount (the largest amount_eur first) | updated_asc | updated_desc | created_asc | created_desc. Page an incremental window with updated_asc."),
    amounts: tuple = Depends(amount_range),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    include_body: bool = include_body_param(),
):
    if order not in _ORDERS and order not in SYNC_ORDERS:
        raise HTTPException(status_code=400, detail=f"order must be one of {list(_ORDERS) + list(SYNC_ORDERS)}")
    if item_type and item_type not in ITEM_TYPES:
        raise HTTPException(status_code=400, detail=f"item_type must be one of {list(ITEM_TYPES)}")
    window = validate_window(created_from, created_to, updated_from, updated_to)
    amounts = amounts if isinstance(amounts, tuple) else (None, None)     # called directly, outside a request
    u = _sources(q, programme)
    where = []
    if item_type:
        where.append(u.c.item_type == item_type)
    if body:
        where.append(u.c.body_code == body.strip().lower())
    if status:
        where.append(func.lower(u.c.status) == status.strip().lower())
    if country:
        where.append(u.c.country == country.strip().upper())
    if programme:
        where.append(u.c.programme.ilike(f"%{programme.strip()}%"))
    if deadline_from:
        where.append(u.c.deadline >= deadline_from)
    if deadline_to:
        where.append(u.c.deadline < datetime.combine(deadline_to, time.max))
    start, end = published_from or since or from_, published_to or until or to
    if start:
        where.append(u.c.document_date >= start)
    if end:
        where.append(u.c.document_date < datetime.combine(end, time.max))
    for key, col, op in (("created_from", u.c.creation_date, "ge"), ("created_to", u.c.creation_date, "le"),
                         ("updated_from", u.c.updated_date, "ge"), ("updated_to", u.c.updated_date, "le")):
        if window[key] is not None:
            where.append(getattr(col, f"__{op}__")(window[key]))
    if amounts[0] is not None:
        where.append(u.c.amount_eur >= amounts[0])
    if amounts[1] is not None:
        where.append(u.c.amount_eur <= amounts[1])
    # One scan: the page carries the total (a q over every source's text is the slow part). A page past
    # the end has no row to carry it, so only then is it counted on its own.
    query = select(u.c.src, u.c.rid, func.count().over().label("total")).where(and_(*where)).order_by(*_order_by(u, order))
    rows = db.execute(stable(query, *_tiebreak(u, order)).offset((page - 1) * limit).limit(limit)).fetchall()
    if rows:
        total = rows[0].total
    else:
        total = (db.execute(select(func.count()).select_from(u).where(and_(*where))).scalar() or 0) if page > 1 else 0
    base = str(request.base_url).rstrip("/")
    data = _build(db, rows, include_body, base, _item_routes(request.app))
    return build_envelope(data, total, page, limit,
                          updated_from=window["updated_from"], updated_to=window["updated_to"])
