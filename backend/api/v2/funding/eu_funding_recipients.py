"""Funding & Tenders database — EU Financial Transparency System (FTS).
/api/v2/funding/eu-funding-recipients — grouped under "Funded Projects".

Who actually received EU money under direct management (the recipient side of
funded projects). Backed by economy_items (body_code 'commission' — FTS is a
Commission system — item_type 'funding_recipient') and, since 26 Oct 2026, the FTS
file's own columns (fts_commitments, migration 313; api/v2/funding/_fts.py). Until then
the list served the record as text only, with q as its one filter: on 21 Oct a partner
search sent `department=CNECT` and got the whole table back.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.v1._change_window import SYNC_ORDERS, SYNC_PARAMS_DOC, UpperBoundDatetime, sql_order, sql_window, validate_window
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope
from services.funding.shared_fields import with_body_names
from core.database import get_db
from models.user import User

from . import _fts

router = APIRouter()

_ORDERS = {"recent", "oldest", "title", "amount"}
_ORDER_SQL = {
    "recent": f"{_fts.DATE_SORT} DESC NULLS LAST, e.id DESC",
    "oldest": f"{_fts.DATE_SORT} ASC NULLS LAST, e.id ASC",
    "title": "e.title ASC, e.id ASC",
    "amount": "c.beneficiary_amount_eur DESC NULLS LAST, e.id DESC",
}

_DESC = f"""**What it does**
Who received EU money under direct management, from the EU Financial Transparency System (FTS): one item per beneficiary of a legal commitment (a grant, a procurement contract, a contribution...). Each item carries the FTS file's own values: `beneficiary`, `country`, `city`, `amount_eur` (this beneficiary's contracted amount) and `commitment_total_eur` (the whole commitment's, shared by its beneficiaries), `funding_type`, `programme`, `dg` (the department that pays), `subject`, `is_coordinator`, `beneficiary_type`, `registration_number`, `vat_number`, `call_id`, `project_id` (the grant agreement: the project at `/api/v2/funding/ft-funded-projects/{{project_id}}` when Brubru holds it), `contract_ref`, `year`.

**When to use it**
Finding partners and competitors: who a DG paid, for what, how much; which organisations coordinate grants under a programme; what one organisation received (by VAT number). For one row per organisation, matched by subject, use `/api/v2/funding/partners`.

**Input**
- `q` — words in the record (beneficiary, subject, programme, department).
- `dg` — the paying department, part of its name (`CNECT`, `CINEA`); `department` and `responsible_department` are the same filter.
- `funding_type` — part of the FTS type of contract (`Action Grant`, `Advisory`, `Contribution`).
- `programme` — part of the FTS name (`Horizon Europe`). `country` — an ISO-2 code (`ES`; EL and GR, UK and GB are the same) or part of the English name FTS writes (`Spain`); 712 of 187,761 records (28 Oct 2026) carry a name cut short in the file (`Republ`) and are found by name only.
- `year` — the FTS file's year (2024, 2025 held).
- `min_amount_eur`, `max_amount_eur` — this beneficiary's amount at least / at most.
- `coordinator` — `true` for coordinators only.
- `project_id`, `call_id`, `vat` — exact.
- `published_from`, `published_to` — the record's date (`document_date`: the project start where FTS gives one); `since`, `until`, `from`, `to` are aliases. {SYNC_PARAMS_DOC.replace(chr(10), ' ')}
- `order` — recent (default) | oldest | title | amount | updated_asc | updated_desc | created_asc | created_desc. `page`, `limit` (default 50, max 200), `include_body` (default true).

**Try it**
```
GET /api/v2/funding/eu-funding-recipients?dg=CNECT&q=study&order=amount
GET /api/v2/funding/eu-funding-recipients?programme=Horizon%20Europe&coordinator=true&country=Spain
GET /api/v2/funding/eu-funding-recipients?project_id=101191044
```

**You get back**
A paginated envelope. Each item carries the fields above, `self`, and the 5 datapoints (`public_url` = the FTS record; `body_txt` / `body_html` on the list unless `include_body=false`, and on the item route). Rows the current FTS file no longer lists (the Commission revised their amount, and the revised row is stored beside them) carry the text only, with the fields null.

**Data freshness**
The FTS files for 2024 and 2025 (ec.europa.eu/budget/financial-transparency-system), read every Sunday (commission-heavy tier, 07:00 UTC); the file's columns are re-read in the same run."""


@router.get("/eu-funding-recipients", response_model=PaginatedResponse[_fts.FtsItem], tags=["v2-funding"],
            summary="EU funding recipients — who received EU money, how much, for what (FTS)",
            description=_DESC)
async def list_recipients(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
    q: Optional[str] = Query(None, description="Words in the record (beneficiary, subject, programme, department)."),
    dg: Optional[str] = Query(None, description="The paying department: part of its name, e.g. CNECT."),
    department: Optional[str] = Query(None, description="Same as dg."),
    responsible_department: Optional[str] = Query(None, description="Same as dg."),
    funding_type: Optional[str] = Query(None, description="Part of the FTS type of contract, e.g. Action Grant, Advisory."),
    programme: Optional[str] = Query(None, description="Part of the FTS programme name."),
    country: Optional[str] = Query(None, description="The beneficiary's country: an ISO-2 code (BE; EL and GR, UK and GB are the same), or part of its English name as FTS writes it (Belgium)."),
    year: Optional[int] = Query(None, description="The FTS file's year."),
    min_amount_eur: Optional[float] = Query(None, ge=0, description="This beneficiary's amount at least, EUR."),
    max_amount_eur: Optional[float] = Query(None, ge=0, description="This beneficiary's amount at most, EUR."),
    coordinator: Optional[bool] = Query(None, description="true: coordinators only; false: the other beneficiaries."),
    project_id: Optional[str] = Query(None, description="Grant agreement number, exact."),
    call_id: Optional[str] = Query(None, description="Call identifier, exact."),
    vat: Optional[str] = Query(None, description="VAT number, exact (spaces ignored)."),
    published_from: Optional[date] = Query(None, description="The record's date (`document_date`: the project start where FTS gives one) on or after (YYYY-MM-DD); `since` and `from` are aliases."),
    published_to: Optional[date] = Query(None, description="The record's date on or before (YYYY-MM-DD); `until` and `to` are aliases."),
    since: Optional[date] = Query(None, description="Project start on/after (YYYY-MM-DD). `from` is accepted as an alias."),
    until: Optional[date] = Query(None, description="Project start on/before (YYYY-MM-DD). `to` is accepted as an alias."),
    from_: Optional[date] = Query(None, alias="from", include_in_schema=False),
    to: Optional[date] = Query(None, include_in_schema=False),
    created_from: Optional[datetime] = Query(None, description="First recorded by Brubru on or after (ISO date or datetime, UTC)."),
    created_to: Optional[UpperBoundDatetime] = Query(None, description="First recorded by Brubru on or before; a bare date covers the whole day."),
    updated_from: Optional[datetime] = Query(None, description="Row or FTS values last changed on or after. The incremental-sync filter."),
    updated_to: Optional[UpperBoundDatetime] = Query(None, description="Last changed on or before; a bare date covers the whole day."),
    order: str = Query("recent", description="recent | oldest | title | amount | updated_asc | updated_desc | created_asc | created_desc."),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    include_body: bool = Query(True, description="Return body_txt / body_html on every item of the list (default true)."),
):
    if order not in _ORDERS and order not in SYNC_ORDERS:
        raise HTTPException(status_code=400, detail=f"order must be one of {sorted(_ORDERS) + list(SYNC_ORDERS)}")
    window = validate_window(created_from, created_to, updated_from, updated_to)
    where: list = []
    params: dict = {"limit": limit, "offset": (page - 1) * limit}
    _fts.filters(where, params, dg=dg or department or responsible_department, funding_type=funding_type,
                 programme=programme, country=country, year=year, min_amount_eur=min_amount_eur, max_amount_eur=max_amount_eur,
                 coordinator=coordinator, project_id=project_id, call_id=call_id, vat=vat)
    if q:
        where.append("e.search_vector @@ plainto_tsquery('english', :q)"); params["q"] = q
    since, until = published_from or since or from_, published_to or until or to
    if since:
        where.append(f"{_fts.DATE_SORT} >= :since"); params["since"] = since
    if until:
        where.append(f"{_fts.DATE_SORT} < CAST(:until AS date) + 1"); params["until"] = until
    sql_window(where, params, window, "e.creation_date", _fts.UPDATED)
    clause = _fts.FROM + "".join(f" AND {w}" for w in where)
    total = db.execute(text(f"SELECT count(*) {clause}"), params).scalar() or 0
    order_sql = sql_order(order, "e.creation_date", _fts.UPDATED, "e.id") or _ORDER_SQL[order]
    rows = db.execute(text(f"SELECT {_fts.cols(include_body)} {clause} ORDER BY {order_sql} "
                           "LIMIT :limit OFFSET :offset"), params).fetchall()
    return build_envelope(with_body_names(db, [_fts.to_item(r, with_body=include_body) for r in rows]), total, page, limit,
                          updated_from=window["updated_from"], updated_to=window["updated_to"])


@router.get("/eu-funding-recipients/{item_id}", response_model=_fts.FtsItem, tags=["v2-funding"],
            summary="One EU funding recipient (the full FTS record)",
            description="""**What it does**
One FTS beneficiary row in full: the file's own values and the record as text.

**When to use it**
After the list (or a `/funding/partners` match), to read one payment's whole record.

**Input**
`item_id` — the `id` from the list (each item's `self` is this route).

**Try it**
```
GET /api/v2/funding/eu-funding-recipients?project_id=101191044
```
then follow an item's `self`.

**You get back**
One item with the same fields as the list, `body_txt` and `body_html` included, or 404.

**Data freshness**
As the list: the FTS files for 2024 and 2025, read every Sunday.""")
async def get_recipient(
    request: Request,
    item_id: int = PathParam(..., description="Brubru item id from the list."),
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
):
    r = db.execute(text(f"SELECT {_fts.cols(True)} {_fts.FROM} AND e.id = :id"), {"id": item_id}).fetchone()
    if r is None:
        raise HTTPException(status_code=404, detail=f"No EU funding recipient with id {item_id}")
    return with_body_names(db, [_fts.to_item(r, with_body=True)])[0]


# /funding/all points each FTS row at this route (api/v2/funding/funding_all.py).
get_recipient.brubru_item_key = ("commission", "funding_recipient")
