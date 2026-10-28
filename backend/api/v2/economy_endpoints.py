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
from api.v1._row_dates import row_updated
from services.funding.shared_fields import with_body_names
from api.v1._change_window import (SYNC_ORDERS, SYNC_PARAMS_DOC, UpperBoundDatetime, sql_order,
                                   sql_window, validate_window)

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
# Procurement routes (procurement=True): some procedures have no published
# publication date (Cedefop 2010-2014, 70 of 464), and falling back to the INGEST
# time put 2010 tenders at the top of a newest-first list. Fall back to the
# deadline first. Kept separate from _ORDER_SQL because /funding/all reuses that on
# a UNION that has no deadline column.
_PROC_DATE_SORT = "coalesce(document_date, deadline, creation_date)"
# The ORDER uses only the item's own dates: a procedure with neither a publication
# date nor a deadline (EIB forecast-only and old pages, 38 rows on 1 Oct 2026) sorted
# by its ingest time and topped every newest-first list. It now goes last; the date
# FILTER keeps the creation_date fallback so undated items stay findable.
_PROC_ORDER_DATE = "coalesce(document_date, deadline)"
_PROC_ORDER_SQL = {
    "recent": f"{_PROC_ORDER_DATE} DESC NULLS LAST, id DESC",
    "oldest": f"{_PROC_ORDER_DATE} ASC NULLS LAST, id ASC",
    "title": "title ASC, id ASC",
}


class _DataPoints(BaseModel):
    """The 5 mandatory Brubru datapoints — present even when null."""
    public_url: Optional[str] = Field(None, description="Canonical URL of the item on the institution's own website.")
    body_txt: Optional[str] = Field(None, description="Plain-text body (full on detail endpoints; null on list).")
    body_html: Optional[str] = Field(None, description="HTML body (full on detail endpoints; null on list).")
    document_date: Optional[datetime] = Field(None, description="The item's own published date.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested the item.")
    updated_date: Optional[datetime] = Field(None, description="When this record last changed, for incremental sync. Null when the source table keeps no change signal.")


class EconomyItem(_DataPoints):
    id: int = Field(..., description="Stable Brubru item id (use it on the detail endpoint).")
    body_code: str = Field(..., description="Body code: 'ecb' or 'ecb_ssm'.")
    item_type: str = Field(..., description="news | publication | event | legal.")
    title: str
    summary: Optional[str] = None
    source_kind: Optional[str] = Field(None, description="How the item was ingested: rss | html | pdf | cellar.")


class ProcurementItem(EconomyItem):
    """An EconomyItem for a procurement procedure (tender or call). The three extra
    fields reuse the names of the Funding & Tenders routes (/funding/ft-calls-for-tenders):
    no new datapoints (Victor, 30 Sep 2026). document_date is the publication date."""
    tender_reference: Optional[str] = Field(None, description="The procedure's reference as published by the body, e.g. CEDEFOP/2026/OP/0012.")
    status: Optional[str] = Field(None, description="open | forthcoming | closed, as on the Funding & Tenders routes. 'open' only while the deadline is ahead.")
    deadline: Optional[datetime] = Field(None, description="Submission deadline; the extended closing date when the body extended it.")


_BODY_NAME_DOC = "The body's name, as Brubru's directory of EU bodies gives it for body_code."
_AMOUNT_EUR_DOC = "The item's main figure in euros; null where the item states none."


class FundingEconomyItem(EconomyItem):
    """An item of a funding list (the funding standard's shared fields, 28 Oct 2026). A news item or
    event has no status and no amount: both stay null."""
    status: Optional[str] = Field(None, description="open | forthcoming | closed for a call or tender; on /funding/all the source's own word for a cohesion programme or Solidarity Fund case; null for news, events and payments.")
    body_name: Optional[str] = Field(None, description=_BODY_NAME_DOC)
    amount_eur: Optional[float] = Field(None, description=_AMOUNT_EUR_DOC)


class FundingProcurementItem(ProcurementItem):
    """A procurement procedure on a funding list, with the funding standard's shared fields. The
    agencies' pages state no value Brubru reads, so amount_eur stays null."""
    body_name: Optional[str] = Field(None, description=_BODY_NAME_DOC)
    amount_eur: Optional[float] = Field(None, description=_AMOUNT_EUR_DOC)


def _as_funding(db: Session, items: list, procurement: bool) -> list:
    """The factory's items with the funding standard's shared fields (body_name from body_code)."""
    cls = FundingProcurementItem if procurement else FundingEconomyItem
    return with_body_names(db, [cls(**i.model_dump()) for i in items])


class ProcurementDocument(_DataPoints):
    """One file attached to a procurement procedure (table procurement_documents,
    migration 263). The text is extracted from the file; the file itself is not stored.
    public_url is the procedure page that publishes the file; file_url is the file."""
    id: str = Field(..., description="Stable Brubru document id (UUID).")
    self: Optional[str] = Field(None, description="URL of this document on the Brubru API (full text).")
    procedure_id: int = Field(..., description="Brubru id of the procedure it belongs to.")
    tender_reference: Optional[str] = Field(None, description="The procedure's reference as published by the body.")
    title: Optional[str] = Field(None, description="The file's title as the body lists it.")
    file_url: str = Field(..., description="The file's address. For a file inside a ZIP: the archive address + '#' + its path in the archive.")
    parent_file_url: Optional[str] = Field(None, description="For a file inside a ZIP: the archive's address.")
    file_name: Optional[str] = None
    file_format: Optional[str] = Field(None, description="pdf | doc | docx | xls | xlsx | ...")
    file_size: Optional[int] = Field(None, description="Size in bytes.")
    language: Optional[str] = Field(None, description="Language code as the body labels the file.")
    body_source: Optional[str] = Field(None, description="How the text was obtained: extracted:<format>, or no-text:<reason> (e.g. no-text:no-text-layer for a scanned PDF; no OCR is attempted).")


_DOC_COLS = ("id::text AS id, economy_item_id, tender_reference, title, file_url, parent_file_url, "
             "file_name, file_format, file_size, language, document_date, public_url, body_source, "
             "first_seen, last_updated")


def _row_to_document(r, *, with_body: bool, self_url: str) -> ProcurementDocument:
    return ProcurementDocument(
        id=r.id, self=self_url, procedure_id=r.economy_item_id,
        tender_reference=r.tender_reference, title=r.title, file_url=r.file_url,
        parent_file_url=r.parent_file_url, file_name=r.file_name, file_format=r.file_format,
        file_size=r.file_size, language=r.language, body_source=r.body_source,
        public_url=r.public_url,
        body_txt=(r.body_txt if with_body else None),
        body_html=(r.body_html if with_body else None),
        document_date=r.document_date, creation_date=r.first_seen,
        updated_date=row_updated(r),
    )


def _row_to_item(r, *, with_body: bool, procurement: bool = False) -> EconomyItem:
    if procurement:
        return ProcurementItem(
            **_row_to_item(r, with_body=with_body).model_dump(),
            tender_reference=r.tender_reference, status=r.status, deadline=r.deadline,
        )
    return EconomyItem(
        id=r.id, body_code=r.body_code, item_type=r.item_type, title=r.title,
        summary=r.summary, source_kind=r.source_kind,
        public_url=r.public_url,
        body_txt=(r.body_txt if with_body else None),
        body_html=(r.body_html if with_body else None),
        document_date=r.document_date, creation_date=r.creation_date,
        updated_date=row_updated(r),
    )


# updated_at is the row's change signal (brubru_touch_if_changed, migrations 271 and 296):
# without it in the SELECT, row_updated() found nothing and every item served
# updated_date = null (API audit, 16 Oct 2026: 451 of 451 Cedefop tenders, 3,299 of 3,299
# of their files). Modules that reuse these lists over another table must project it too.
_LIST_COLS = "id, body_code, item_type, title, summary, public_url, document_date, creation_date, source_kind, updated_at"
_DETAIL_COLS = "id, body_code, item_type, title, summary, public_url, body_txt, body_html, document_date, creation_date, source_kind, updated_at"
_PROCUREMENT_COLS = ", tender_reference, status, deadline"


def _list_items(db: Session, body_code: str, item_type: str, q, since, until, order,
                page, limit, include_body: bool = False, procurement: bool = False, window=None,
                status=None, deadline_from=None, deadline_to=None):
    where = ["body_code = :bc", "item_type = :it"]
    params = {"bc": body_code, "it": item_type, "limit": limit, "offset": (page - 1) * limit}
    date_sort = _PROC_DATE_SORT if procurement else _DATE_SORT
    # The incremental-sync window and orders (23 Oct 2026): every factory list carried
    # updated_date and none could be filtered on it, so a partner re-read whole lists to
    # find what changed. updated_at is the change-only signal (brubru_touch_if_changed)
    # and is set on every row; creation_date is when Brubru first stored the row.
    order_sql = (sql_order(order, "creation_date", "updated_at")
                 or (_PROC_ORDER_SQL if procurement else _ORDER_SQL)[order])
    if window:
        sql_window(where, params, window, "creation_date", "updated_at")
    if q:
        where.append("search_vector @@ plainto_tsquery('english', :q)")
        params["q"] = q
    if since:
        where.append(f"{date_sort} >= :since")
        params["since"] = since
    if until:
        where.append(f"{date_sort} < CAST(:until AS date) + 1")
        params["until"] = until
    if status:
        where.append("status = :status")
        params["status"] = status
    if deadline_from:
        where.append("deadline >= :deadline_from")
        params["deadline_from"] = deadline_from
    if deadline_to:
        where.append("deadline < CAST(:deadline_to AS date) + 1")
        params["deadline_to"] = deadline_to
    clause = " AND ".join(where)
    total = db.execute(text(f"SELECT count(*) FROM economy_items WHERE {clause}"), params).scalar() or 0
    # Select the body columns only when asked: they dominate the row size, and
    # the default list is meant to stay cheap.
    cols = _DETAIL_COLS if include_body else _LIST_COLS
    if procurement:
        cols += _PROCUREMENT_COLS
    rows = db.execute(
        text(f"SELECT {cols} FROM economy_items WHERE {clause} "
             f"ORDER BY {order_sql} LIMIT :limit OFFSET :offset"), params
    ).fetchall()
    return [_row_to_item(r, with_body=include_body, procurement=procurement) for r in rows], total


def _get_item(db: Session, body_code: str, item_type: str, item_id: int, procurement: bool = False):
    cols = _DETAIL_COLS + (_PROCUREMENT_COLS if procurement else "")
    r = db.execute(
        text(f"SELECT {cols} FROM economy_items "
             "WHERE id = :id AND body_code = :bc AND item_type = :it"),
        {"id": item_id, "bc": body_code, "it": item_type},
    ).fetchone()
    return _row_to_item(r, with_body=True, procurement=procurement) if r else None


_DESC_LIST = """**What it does**
Lists {body}'s {noun}, newest first. {extra}

**When to use it**
Track what {acro} is publishing without scraping its website. Filter by free text or date, page through the archive, then call the detail endpoint for an item's full body.

**Input**
`q` free-text search, `since` / `until` (YYYY-MM-DD) on the item date{filters}, `order` (recent | oldest | title), `page`, `limit` ({limits}), `include_body`.
<<SYNC_PARAMS>>

**Try it**
```
GET {path}?order=recent&limit=10
```

**You get back**
A paginated envelope of items. Each carries the 5 datapoints. {bodies}

**Data freshness**
Refreshed from {source}."""
_BODIES_OFF = ("`body_txt` / `body_html` are null on the list by default — **pass `include_body=true` to get "
               "them in bulk**, or call the detail endpoint for a single item.")
_BODIES_ON = ("`body_txt` / `body_html` are on every item by default (the funding standard); pass "
              "`include_body=false` for a lighter page.")
# The incremental-sync parameters, worded once for every endpoint that offers them.
_DESC_LIST = _DESC_LIST.replace("<<SYNC_PARAMS>>", SYNC_PARAMS_DOC)

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


_DESC_DOCS = """**What it does**
Lists the files {body} attached to one procedure from `{path}` (terms of reference, forms, questions and answers, corrigenda, award notices), with the text extracted from each file.

**When to use it**
Read what a procedure actually asks for without downloading and opening every file. Pass `include_body=true` for the text of every file, or call the single-document endpoint.

**Input**
`item_id` from the list endpoint; `include_body` (default false), `page`, `limit` (max 100).

**Try it**
```
GET {path}/{{item_id}}/documents
```

**You get back**
A paginated envelope of files in the order the body lists them. A file inside a ZIP archive is its own entry (`parent_file_url` names the archive). `body_source` says how the text was obtained; a scanned PDF says `no-text:no-text-layer` rather than guessing.

**Data freshness**
Files are read daily, for live and recent procedures, from the body's procedure pages or its Funding & Tenders portal notices."""

_DESC_DOC = """**What it does**
Returns one file of a procedure listed at `{path}`, with its full extracted text.

**When to use it**
After listing a procedure's documents, fetch one file's complete text.

**Input**
`item_id` (the procedure) and `document_id` (from the documents list).

**Try it**
```
GET {path}/{{item_id}}/documents/{{document_id}}
```

**You get back**
One document with `body_txt` and `body_html` and the 5 datapoints (`public_url` is the procedure page that publishes the file)."""


# The funding standard's filters (Phase 2, 27 Oct 2026), declared as a dependency so that only the
# funding lists gain them: every other folder registers the empty one and keeps its parameters.
_STATUSES = ("open", "forthcoming", "closed")


def _no_filters() -> dict:
    return {}


def _funding_filters(
    published_from: Optional[date] = Query(None, description="Published on or after (YYYY-MM-DD); `since` and `from` are aliases."),
    published_to: Optional[date] = Query(None, description="Published on or before (YYYY-MM-DD); `until` and `to` are aliases."),
) -> dict:
    return {"published_from": published_from, "published_to": published_to}


def _funding_procurement_filters(
    published_from: Optional[date] = Query(None, description="Published on or after (YYYY-MM-DD); `since` and `from` are aliases."),
    published_to: Optional[date] = Query(None, description="Published on or before (YYYY-MM-DD); `until` and `to` are aliases."),
    status: Optional[str] = Query(None, description="open | forthcoming | closed."),
    deadline_from: Optional[date] = Query(None, description="Deadline on or after (YYYY-MM-DD)."),
    deadline_to: Optional[date] = Query(None, description="Deadline on or before (YYYY-MM-DD)."),
) -> dict:
    if status is not None and status not in _STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {list(_STATUSES)}")
    return {"published_from": published_from, "published_to": published_to, "status": status,
            "deadline_from": deadline_from, "deadline_to": deadline_to}


def register_resource(router, *, body_code, item_type, slug, noun, body_name, acronym,
                      source, tag, extra="", procurement=False, documents=False, funding_standard=False):
    """Add list + detail GET routes for one (body, resource) onto `router`.
    documents=True (procurement routes whose files are written to procurement_documents)
    adds {slug}/{item_id}/documents and {slug}/{item_id}/documents/{document_id}.
    funding_standard=True applies the funding standard's defaults to the list (Victor, 23 Oct 2026:
    50 items per page, at most 200, bodies included); every other body folder keeps its own."""
    limit_default, limit_max = (50, 200) if funding_standard else (20, 100)
    filters = (_funding_procurement_filters if procurement else _funding_filters) if funding_standard else _no_filters
    noun_singular = noun.rstrip("s") if noun.endswith("s") else noun
    path_hint = slug if slug.startswith("/") else f"/{slug}"
    if funding_standard:
        item_model = FundingProcurementItem if procurement else FundingEconomyItem
    else:
        item_model = ProcurementItem if procurement else EconomyItem

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
        created_from: Optional[datetime] = Query(None, description="First recorded by Brubru on or after (ISO date or datetime, UTC)."),
        created_to: Optional[UpperBoundDatetime] = Query(None, description="First recorded by Brubru on or before; a bare date covers the whole day."),
        updated_from: Optional[datetime] = Query(None, description="Content last changed on or after (ISO date or datetime, UTC). The incremental-sync filter."),
        updated_to: Optional[UpperBoundDatetime] = Query(None, description="Content last changed on or before; a bare date covers the whole day."),
        order: str = Query("recent", description="recent | oldest | title | updated_asc | updated_desc | created_asc | created_desc. Page an incremental window with updated_asc."),
        page: int = Query(1, ge=1),
        limit: int = Query(limit_default, ge=1, le=limit_max),
        include_body: bool = Query(
            funding_standard,
            description=(
                "Return `body_txt` / `body_html` on every item in the list (default true on the "
                "funding lists; false elsewhere, where bodies dominate the payload)."
            ),
        ),
        standard: dict = Depends(filters),
    ):
        if order not in _ORDERS and order not in SYNC_ORDERS:
            raise HTTPException(status_code=400, detail=f"order must be one of {sorted(_ORDERS) + list(SYNC_ORDERS)}")
        standard = standard if isinstance(standard, dict) else {}      # called directly, outside a request
        since = since or from_ or standard.get("published_from")
        until = until or to or standard.get("published_to")
        window = validate_window(created_from, created_to, updated_from, updated_to)
        items, total = _list_items(db, body_code, item_type, q, since, until, order,
                                   page, limit, include_body=include_body,
                                   procurement=procurement, window=window, status=standard.get("status"),
                                   deadline_from=standard.get("deadline_from"), deadline_to=standard.get("deadline_to"))
        if funding_standard:
            items = _as_funding(db, items, procurement)
        return build_envelope(items, total, page, limit,
                              updated_from=window["updated_from"], updated_to=window["updated_to"])

    async def detail_ep(
        request: Request,
        item_id: int = PathParam(..., description="Brubru item id from the list endpoint."),
        db: Session = Depends(get_db),
        user: User = Depends(api_user_with_rate_limit),
    ):
        item = _get_item(db, body_code, item_type, item_id, procurement=procurement)
        if item is None:
            raise HTTPException(status_code=404, detail=f"No {body_name} {noun_singular} with id {item_id}")
        return _as_funding(db, [item], procurement)[0] if funding_standard else item
    # What this item route serves, so an aggregate (/funding/all) can point each of its rows at
    # its own route without a second copy of the slug table (core.self_links.item_route_for).
    detail_ep.brubru_item_key = (body_code, item_type)

    router.add_api_route(
        path_hint, list_ep, methods=["GET"],
        response_model=PaginatedResponse[item_model], tags=[tag],
        summary=f"{body_name} — {noun} (newest first)",
        description=_DESC_LIST.format(body=body_name, noun=noun, acro=acronym, path=path_hint,
                                      source=source, extra=extra,
                                      limits=f"default {limit_default}, max {limit_max}",
                                      filters=("" if not funding_standard else
                                               " (`published_from` / `published_to` are the same window)"
                                               + (", `status` (open | forthcoming | closed), `deadline_from` / "
                                                  "`deadline_to` (YYYY-MM-DD)" if procurement else "")),
                                      bodies=(_BODIES_ON if funding_standard else _BODIES_OFF)),
    )
    router.add_api_route(
        f"{path_hint}/{{item_id}}", detail_ep, methods=["GET"],
        response_model=item_model, tags=[tag],
        summary=f"{body_name} — one {noun_singular} (full body)",
        description=_DESC_DETAIL.format(body=body_name, noun_singular=noun_singular, path=path_hint,
                                        source=source),
    )
    if not documents:
        return

    def _procedure_or_404(db: Session, item_id: int) -> None:
        hit = db.execute(
            text("SELECT 1 FROM economy_items WHERE id = :id AND body_code = :bc AND item_type = :it"),
            {"id": item_id, "bc": body_code, "it": item_type},
        ).fetchone()
        if hit is None:
            raise HTTPException(status_code=404, detail=f"No {body_name} {noun_singular} with id {item_id}")

    def _doc_self(request: Request, doc_id: str) -> str:
        # Built from the path that was called, so it cannot disagree with the mount.
        path = request.url.path.rstrip("/")
        if not path.endswith("/documents"):
            path = path.rsplit("/", 1)[0]
        return f"{str(request.base_url).rstrip('/')}{path}/{doc_id}"

    async def documents_ep(
        request: Request,
        item_id: int = PathParam(..., description="Brubru id of the procedure, from the list endpoint."),
        db: Session = Depends(get_db),
        user: User = Depends(api_user_with_rate_limit),
        page: int = Query(1, ge=1),
        limit: int = Query(50, ge=1, le=100),
        include_body: bool = Query(False, description="Return each file's extracted text."),
    ):
        _procedure_or_404(db, item_id)
        total = db.execute(text("SELECT count(*) FROM procurement_documents WHERE economy_item_id = :i"),
                           {"i": item_id}).scalar() or 0
        cols = _DOC_COLS + (", body_txt, body_html" if include_body else "")
        # first_seen then file_url: the order the files were found; id last makes it total.
        rows = db.execute(
            text(f"SELECT {cols} FROM procurement_documents WHERE economy_item_id = :i "
                 "ORDER BY first_seen, file_url, id LIMIT :limit OFFSET :offset"),
            {"i": item_id, "limit": limit, "offset": (page - 1) * limit},
        ).fetchall()
        items = [_row_to_document(r, with_body=include_body,
                                  self_url=_doc_self(request, r.id)) for r in rows]
        return build_envelope(items, total, page, limit)

    async def document_ep(
        request: Request,
        item_id: int = PathParam(..., description="Brubru id of the procedure."),
        document_id: str = PathParam(..., description="Document id (UUID) from the documents list."),
        db: Session = Depends(get_db),
        user: User = Depends(api_user_with_rate_limit),
    ):
        _procedure_or_404(db, item_id)
        r = db.execute(
            text(f"SELECT {_DOC_COLS}, body_txt, body_html FROM procurement_documents "
                 "WHERE economy_item_id = :i AND id::text = :d"),
            {"i": item_id, "d": document_id},
        ).fetchone()
        if r is None:
            raise HTTPException(status_code=404, detail=f"No document {document_id} on {body_name} {noun_singular} {item_id}")
        return _row_to_document(r, with_body=True, self_url=_doc_self(request, r.id))

    router.add_api_route(
        f"{path_hint}/{{item_id}}/documents", documents_ep, methods=["GET"],
        response_model=PaginatedResponse[ProcurementDocument], tags=[tag],
        summary=f"{body_name} — the files of one procedure, with their text",
        description=_DESC_DOCS.format(body=body_name, noun_singular=noun_singular, path=path_hint),
    )
    router.add_api_route(
        f"{path_hint}/{{item_id}}/documents/{{document_id}}", document_ep, methods=["GET"],
        response_model=ProcurementDocument, tags=[tag],
        summary=f"{body_name} — one file of a procedure (full text)",
        description=_DESC_DOC.format(body=body_name, noun_singular=noun_singular, path=path_hint),
    )


# ---------------------------------------------------------------------------
# Single-body own-folder factory — used by the single-market / digital agencies
# (BEREC, ACER, EIT, ENISA, eu-LISA, EUIPO, CPVO). Each is one body in its own
# folder, so its resources sit directly under the folder prefix plus a small
# directory endpoint. Mirrors the hand-written ESM folder.
# ---------------------------------------------------------------------------
def make_single_body_folder(*, body_code, prefix, body_name, acronym, tag, resources):
    """Return an APIRouter for a single-body own-folder.

    resources: list of dicts with keys item_type, slug, noun, source, extra, and procurement
    (True for tenders and calls: the items carry tender_reference, status and deadline).
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
            source=r["source"], extra=r.get("extra", ""), procurement=r.get("procurement", False),
        )
    return router
