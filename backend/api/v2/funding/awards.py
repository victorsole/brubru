"""GET /api/v2/funding/awards: who was awarded EU money, in one list.

Funding standard Phase 3c (proposal of 23 Oct 2026 §6; Victor's decision of 30 Oct 2026). One list over
the EU-funded projects (`ft_funded_projects`, /ft-funded-projects), the beneficiaries' commitments in the
EU Financial Transparency System (FTS, /eu-funding-recipients; /international-cooperation is a view of the
same rows, so they are served once) and the EU bodies' contract award notices on TED (/tender-awards).

The three sources share no exact key for one award (measured 30 Oct 2026: 1 of 11,478 TED contract
references is an FTS commitment reference), so every row is served. A project and its beneficiaries' FTS
lines are different items about the same grant (46,200 FTS lines under 9,066 projects Brubru holds):
Victor's decision is to serve both, each FTS line linking its project in `project`; their amounts are the
same money.

How a page is made: each source is filtered, ordered and cut at offset + limit on its own (so its index
serves the order), the three are merged in the same total order, and each row of the page is built by its
own list's builder, so an item here is the same item as on its own list and `self` opens it there. The
total is the sum of each source's count. `q` is each list's own full-text search (each has its index).
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from api.v1 import funding_tenders_collections as ft
from api.v1._change_window import SYNC_ORDERS, UpperBoundDatetime, validate_window
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope
from core.database import get_db
from models.funding_tenders import FtFundedProject
from models.user import User
from services.funding.countries import both_styles
from services.funding.programme_codes import named_codes
from services.funding.shared_fields import AMOUNT_EUR_RULE, with_body_names
from . import _fts
from . import tender_awards as ta
from ._standard import amount_range, include_body_param

router = APIRouter()

ITEM_TYPES = ("funded_project", "funding_recipient", "tender_award")
_ORDERS = ("recent", "oldest", "amount")
_ITEM_PATHS = {"project": "/api/v2/funding/ft-funded-projects/{}", "fts": "/api/v2/funding/eu-funding-recipients/{}",
               "ted_award": "/api/v2/funding/tender-awards/{}"}

# The projects list's own date (its publication, else a start already passed), compiled from its expression.
_PROJECT_DATE = str(ft._PROJECT_DATE_SQL.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))

# Each source with the union's columns; {q} is each list's own full-text condition (or nothing).
_PROJECT_SIDE = f"""
SELECT 'project' AS src, ft_funded_projects.id::text AS rid, 'funded_project'::text AS item_type, 'ftportal'::text AS body_code,
       ({_PROJECT_DATE})::timestamptz AS document_date, ft_funded_projects.scraped_at AT TIME ZONE 'UTC' AS creation_date,
       ft_funded_projects.last_updated AT TIME ZONE 'UTC' AS updated_date, ft_funded_projects.status::text AS status,
       ({ft._PROJECT_EUR})::numeric AS amount_eur, ft_funded_projects.coordinator_country::text AS country,
       ft_funded_projects.framework_programme::text AS programme
FROM ft_funded_projects WHERE NOT ft_funded_projects.is_test{{q}}"""
_FTS_SIDE = f"""
SELECT 'fts' AS src, e.id::text AS rid, 'funding_recipient'::text AS item_type, 'commission'::text AS body_code,
       {_fts.DATE_SORT} AS document_date, e.creation_date AS creation_date, {_fts.UPDATED} AS updated_date,
       NULL::text AS status, c.beneficiary_amount_eur::numeric AS amount_eur, c.country_code::text AS country,
       c.programme::text AS programme
{_fts.FROM}{{q}}"""
_TED_SIDE = f"""
SELECT 'ted_award' AS src, n.publication_number::text AS rid, 'tender_award'::text AS item_type, n.body_code::text AS body_code,
       n.publication_date::timestamptz AS document_date, n.first_seen AS creation_date, n.last_updated AS updated_date,
       'closed'::text AS status, ({ta._AMOUNT_EUR})::numeric AS amount_eur, n.buyer_country::text AS country,
       NULL::text AS programme
FROM ted_award_notices n WHERE n.superseded_by IS NULL{{q}}"""
_Q = {"project": f" AND {ft._PROJECT_TSV} @@ websearch_to_tsquery('english', :q)",
      "fts": " AND e.search_vector @@ plainto_tsquery('english', :q)",
      "ted_award": f" AND {ta._TSV} @@ websearch_to_tsquery('english', :q)"}


_SIDES = (("project", _PROJECT_SIDE), ("fts", _FTS_SIDE), ("ted_award", _TED_SIDE))


def _side(src: str, q: bool) -> str:
    return dict(_SIDES)[src].replace("{q}", _Q[src] if q else "")


def _order_sql(order: str) -> str:
    """The order's columns, then src + rid (unique across the union) in the same direction: a total order."""
    if order in SYNC_ORDERS:
        col = "updated_date" if order.startswith("updated") else "creation_date"
        d = "ASC" if order.endswith("_asc") else "DESC"
        return f"{col} {d}, src {d}, rid {d}"
    return {"recent": "document_date DESC NULLS LAST, src DESC, rid DESC",
            "oldest": "document_date ASC NULLS LAST, src ASC, rid ASC",
            "amount": "amount_eur DESC NULLS LAST, src DESC, rid DESC"}[order]


def _page_sql(order: str, clause: str, q: bool) -> str:
    """The page: each source filtered, ordered and cut at offset + limit on its own (so a source's index
    serves its order: the FTS lines' date order is an index range), then the three merged in the same
    total order. Sorting the whole union instead read every FTS row (60-90 s, 30 Oct 2026)."""
    o = _order_sql(order)
    sides = " UNION ALL ".join(f"(SELECT * FROM ({_side(src, q)}) s{clause} ORDER BY {o} LIMIT :side_limit)"
                               for src, _ in _SIDES)
    return f"SELECT src, rid FROM ({sides}) aw ORDER BY {o} LIMIT :limit OFFSET :offset"


def _count_sql(clause: str, q: bool) -> str:
    return "SELECT " + " + ".join(f"(SELECT count(*) FROM ({_side(src, q)}) s{clause})" for src, _ in _SIDES)


class AwardItem(BaseModel):
    """A funded project, a beneficiary's FTS commitment or a TED award notice, as its own list serves it."""
    model_config = ConfigDict(extra="allow")
    id: Any = Field(..., description="The item's id on its own list: a project's UUID, an FTS line's number, a TED publication number.")
    self: Optional[str] = Field(None, description="This item on its own list (/ft-funded-projects, /eu-funding-recipients or /tender-awards).")
    item_type: str = Field(..., description="funded_project | funding_recipient | tender_award.")
    title: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[str] = Field(None, description="A project's planned | ongoing | ended | terminated | suspended | unknown; closed for an award notice; null for an FTS commitment.")
    body_code: Optional[str] = None
    body_name: Optional[str] = None
    amount_eur: Optional[float] = Field(None, description=f"A project's EU contribution, a beneficiary's FTS amount, an award notice's awarded value, in euros: {AMOUNT_EUR_RULE}. A project's and its beneficiaries' FTS amounts are the same money.")
    public_url: Optional[str] = None
    document_date: Union[datetime, date, None] = None
    creation_date: Union[datetime, date, None] = None
    updated_date: Union[datetime, date, None] = None
    body_txt: Optional[str] = None
    body_html: Optional[str] = None
    project: Optional[str] = Field(None, description="On an FTS commitment: the project it funds, when Brubru holds it.")


def _build(db: Session, rows, include_body: bool, base: str) -> List[dict]:
    """Each page row built by its own list's builder, in the page's order."""
    ids: Dict[str, list] = {}
    for r in rows:
        ids.setdefault(r.src, []).append(r.rid)
    built: Dict[tuple, Any] = {}
    if ids.get("project"):
        recs = db.query(FtFundedProject).filter(FtFundedProject.id.in_(ids["project"])).all()
        built.update({("project", str(r.id)): ft._project_to_item(r) for r in recs})
    if ids.get("fts"):
        recs = db.execute(text(f"SELECT {_fts.cols(True)} {_fts.FROM} AND e.id = ANY(:ids)"),
                          {"ids": [int(i) for i in ids["fts"]]}).fetchall()
        items = _fts.with_projects(db, [_fts.to_item(r, with_body=True) for r in recs], base)
        built.update({("fts", str(i.id)): i for i in items})
    if ids.get("ted_award"):
        recs = db.execute(text(f"SELECT {ta._COLS}, n.body_txt, n.body_html {ta._FROM} AND n.publication_number = ANY(:ids)"),
                          {"ids": ids["ted_award"]}).fetchall()
        winners = ta._winners(db, [r.publication_number for r in recs], base)
        built.update({("ted_award", str(r.publication_number)): ta._item(r, winners.get(r.publication_number, []), True,
                                                                          (r.body_txt, r.body_html)) for r in recs})
    with_body_names(db, list(built.values()))
    out = []
    for r in rows:
        item = built.get((r.src, r.rid))
        if item is None:      # removed between the page query and the build
            continue
        d = item.model_dump()
        key = d.get("project_id") if r.src == "project" else d["id"]
        d["self"] = base + _ITEM_PATHS[r.src].format(quote(str(key), safe=""))
        if not include_body:
            d["body_txt"] = d["body_html"] = None
        out.append(d)
    return out


_DESC = """**What it does**
Who was awarded EU money, in one list: the EU-funded projects (`/ft-funded-projects`: Horizon Europe, Horizon 2020, FP7 from CORDIS and every other programme from the Funding & Tenders Portal), each beneficiary's commitment in the EU Financial Transparency System (`/eu-funding-recipients`: grants, procurement contracts and contributions under direct management, 2024 and 2025) and the EU bodies' contract award notices on TED (`/tender-awards`, since 2024).

**When to use it**
"Who got EU money for this?" across grants and contracts at once, for example `q=hydrogen&order=amount`, or everything awarded in one country: `country=PT`. To work with one source and all its own filters, use its list; each item's `self` opens it there.

**Input**
`q` (each source's own full-text search: every word, any form), `item_type` (funded_project | funding_recipient | tender_award), `status` (a project's planned | ongoing | ended | terminated | suspended; `closed` for award notices), `body` (`ftportal` for projects, `commission` for FTS, an EU body's code for award notices), `country` (two letters: a project's coordinator, an FTS beneficiary, an award notice's buyer), `programme` (a project's or an FTS line's programme: a code such as `HORIZON` or words such as `Horizon Europe`), `published_from`/`published_to` (the item's `document_date`; `since`, `until`, `from`, `to` are aliases), `created_from`/`created_to` and `updated_from`/`updated_to` (incremental sync; a bare date as `_to` covers the whole day), `min_amount_eur`/`max_amount_eur`, `order` (recent | oldest | amount | updated_asc | updated_desc | created_asc | created_desc), `page`, `limit` (default 50, max 200), `include_body` (default true).

**Try it**
```
GET /api/v2/funding/awards?q=hydrogen&order=amount
GET /api/v2/funding/awards?country=PT&item_type=funding_recipient
GET /api/v2/funding/awards?updated_from=2026-10-29&order=updated_asc
```

**You get back**
A paginated list. Each item is the item of its own list, field for field, with `self` (that list's item). A project and its beneficiaries' FTS lines are both served and are the same money: an FTS line names its project in `project` (on 30 Oct 2026, 46,200 FTS lines under 9,066 projects Brubru holds), so do not add a project's `amount_eur` to its lines'. The sources share no key for one contract (an FTS procurement line and a TED award notice may be the same contract and are both served). Superseded award notices are left out, as on `/tender-awards`.

**Data freshness**
As each source: projects every Sunday from 1 November 2026 (until then last read on 6 May for CORDIS and 15 June for the F&T Portal); FTS (the 2024 and 2025 files) every Sunday; award notices daily."""


@router.get("/awards", response_model=PaginatedResponse[AwardItem], tags=["v2-funding"],
            summary="Who was awarded EU money: funded projects, FTS beneficiaries and TED contract awards in one list",
            description=_DESC)
async def list_awards(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
    q: Optional[str] = Query(None, description="Words in the item's text, by each source's own full-text search (every word, any form)."),
    item_type: Optional[str] = Query(None, description="funded_project | funding_recipient | tender_award."),
    status: Optional[str] = Query(None, description="planned | ongoing | ended | terminated | suspended (projects) | closed (award notices). FTS commitments have none."),
    body: Optional[str] = Query(None, description="ftportal (projects), commission (FTS) or an EU body's code (award notices), e.g. ema."),
    country: Optional[str] = Query(None, min_length=2, max_length=2, description="Two letters (EL and GR, UK and GB are the same): a project's coordinator, an FTS beneficiary, an award notice's buyer."),
    programme: Optional[str] = Query(None, description="A project's or an FTS line's programme: part of a code (HORIZON, LIFE) or of its name (Horizon Europe)."),
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
    order: str = Query("recent", description="recent (the newest first) | oldest | amount (the largest amount_eur first) | updated_asc | updated_desc | created_asc | created_desc. Page an incremental window with updated_asc."),
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
    where: list = []
    params: dict = {"limit": limit, "offset": (page - 1) * limit}
    if q and q.strip():
        params["q"] = q.strip()
    if item_type:
        where.append("item_type = :item_type"); params["item_type"] = item_type
    if body:
        where.append("body_code = :body"); params["body"] = body.strip().lower()
    if status:
        where.append("lower(status) = :status"); params["status"] = status.strip().lower()
    if country:
        where.append("upper(country) = ANY(:countries)"); params["countries"] = both_styles(country)
    if programme:
        codes = named_codes(programme)
        where.append("(programme ILIKE :programme" + (" OR programme = ANY(:programme_codes))" if codes else ")"))
        params["programme"] = f"%{programme.strip()}%"
        if codes:
            params["programme_codes"] = codes
    start, end = published_from or since or from_, published_to or until or to
    if start:
        where.append("document_date >= :published_from"); params["published_from"] = start
    if end:
        where.append("document_date < :published_to_end"); params["published_to_end"] = datetime.combine(end, time.max)
    for key, col, op in (("created_from", "creation_date", ">="), ("created_to", "creation_date", "<="),
                         ("updated_from", "updated_date", ">="), ("updated_to", "updated_date", "<=")):
        if window[key] is not None:
            where.append(f"{col} {op} :{key}"); params[key] = window[key]
    if amounts[0] is not None:
        where.append("amount_eur >= :min_amount_eur"); params["min_amount_eur"] = amounts[0]
    if amounts[1] is not None:
        where.append("amount_eur <= :max_amount_eur"); params["max_amount_eur"] = amounts[1]
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    params["side_limit"] = params["offset"] + limit
    rows = db.execute(text(_page_sql(order, clause, "q" in params)), params).fetchall()
    total = db.execute(text(_count_sql(clause, "q" in params)), params).scalar() or 0
    data = _build(db, rows, include_body, str(request.base_url).rstrip("/"))
    return build_envelope(data, total, page, limit,
                          updated_from=window["updated_from"], updated_to=window["updated_to"])
