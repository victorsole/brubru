"""GET /api/v2/funding/budgets: the EU budget money Brubru holds by fund, in one list.

Funding standard Phase 3d (proposal of 23 Oct 2026 §6; Victor's decisions of 30 Oct 2026). One list over
the 2021-2027 cohesion allocations (`eu_cohesion_finances`: ERDF, ESF+, Cohesion Fund, JTF, Interreg,
EMFAF, AMIF, ISF, each on its own list such as /erdf), the EU Solidarity Fund cases (/eusf) and the CAP
fund payments by Member State (/eagf, /eafrd). Money only: the cohesion indicators (/<fund>/outcomes)
count outputs and results in units, not euros, and stay on their own lists. The two CAP rows that are
the EU total of the 27 Member States (`ms = 'TOTAL'`, O102) are left out, so a sum over the list counts
each euro once; /eagf and /eafrd still serve them.

The sources hold different money (a plan's allocation, a disaster grant paid, payments to a Member
State) and share no item, so every row is served. Each page row is built by its own list's builder, so
an item here is the same item as on its own list, and `self` opens it there.
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.v1._change_window import SYNC_ORDERS, UpperBoundDatetime, validate_window
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope
from core.database import get_db
from models.user import User
from services.funding.countries import both_styles
from services.funding.shared_fields import BUDGET_STATUSES, FUND_NAMES, budget_status_sql
from . import cohesion_cap as cap
from . import cohesion_eusf as eusf
from . import cohesion_finances as cf
from ._standard import amount_range, include_body_param
from .funding_all import _item_routes

router = APIRouter()

ITEM_TYPES = ("cohesion_allocation", "solidarity_case", "cap_payment")
_ORDERS = ("amount", "recent", "oldest")

# Each source with the union's columns; {q} is each list's own text condition (or nothing).
_ALLOC_SIDE = f"""
SELECT 'alloc' AS src, id AS rid, 'cohesion_allocation'::text AS item_type, lower(fund) AS body_code,
       document_date, created_at AS creation_date, updated_at AS updated_date,
       ({budget_status_sql('status')})::text AS status, status AS source_status, total::numeric AS amount_eur,
       ms AS country, cci_title AS programme_title
FROM eu_cohesion_finances WHERE TRUE{{q}}"""
_EUSF_SIDE = f"""
SELECT 'eusf' AS src, id AS rid, 'solidarity_case'::text AS item_type, 'eusf'::text AS body_code,
       document_date, created_at AS creation_date, updated_at AS updated_date,
       ({budget_status_sql('status')})::text AS status, status AS source_status,
       round(eusf_grant_paid_meur * 1000000)::numeric AS amount_eur, applicant_country AS country, NULL::text AS programme_title
FROM eu_solidarity_fund WHERE TRUE{{q}}"""
_CAP_SIDE = """
SELECT 'cap' AS src, id AS rid, 'cap_payment'::text AS item_type, lower(fund) AS body_code,
       document_date, created_at AS creation_date, updated_at AS updated_date,
       NULL::text AS status, NULL::text AS source_status, total_eur::numeric AS amount_eur, ms AS country, NULL::text AS programme_title
FROM eu_cap_payments WHERE ms IS DISTINCT FROM 'TOTAL'{q}"""
# Each list's own `q` (a substring, as on /erdf, /eusf, /eagf).
_Q = {"alloc": " AND (cci_title ILIKE :q OR body_txt ILIKE :q)",
      "eusf": " AND (name_of_disaster ILIKE :q OR body_txt ILIKE :q)",
      "cap": " AND body_txt ILIKE :q"}
_SIDES = (("alloc", _ALLOC_SIDE), ("eusf", _EUSF_SIDE), ("cap", _CAP_SIDE))
_BUILDERS = {"alloc": (cf, "eu_cohesion_finances"), "eusf": (eusf, "eu_solidarity_fund"), "cap": (cap, "eu_cap_payments")}


def _union(q: bool) -> str:
    return " UNION ALL ".join(f"({side.replace('{q}', _Q[src] if q else '')})" for src, side in _SIDES)


def _order_sql(order: str) -> str:
    """The order's columns, then src + rid (unique across the union) in the same direction: a total order."""
    if order in SYNC_ORDERS:
        col = "updated_date" if order.startswith("updated") else "creation_date"
        d = "ASC" if order.endswith("_asc") else "DESC"
        return f"{col} {d}, src {d}, rid {d}"
    return {"amount": "amount_eur DESC NULLS LAST, src DESC, rid DESC",
            "recent": "document_date DESC NULLS LAST, src DESC, rid DESC",
            "oldest": "document_date ASC NULLS LAST, src ASC, rid ASC"}[order]


def _funds_named(programme: str) -> List[str]:
    """The funds whose code or name contains the words (ERDF, Regional Development, Solidarity)."""
    p = programme.strip().lower()
    return sorted(code for code, name in FUND_NAMES.items() if p in code or p in name.lower())


class BudgetItem(BaseModel):
    """A cohesion allocation, a Solidarity Fund case or a CAP payment row, as its own list serves it."""
    model_config = ConfigDict(extra="allow")
    id: int = Field(..., description="The item's id on its own list (`self`).")
    self: Optional[str] = Field(None, description="This item on its own list (/erdf, /esf-plus, ... /eusf, /eagf, /eafrd).")
    item_type: str = Field(..., description="cohesion_allocation | solidarity_case | cap_payment.")
    title: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[str] = Field(None, description="adopted for a cohesion programme; accepted | rejected | withdrawn | under_assessment for a Solidarity Fund case; null for a CAP payment row.")
    body_code: Optional[str] = Field(None, description="The fund: erdf, esf, cf, jtf, interreg, emfaf, amif, isf, eusf, eagf or eafrd.")
    body_name: Optional[str] = None
    amount_eur: Optional[float] = Field(None, description="An allocation's total EU amount, a Solidarity Fund grant paid, a CAP fund's payments to the Member State, in euros.")
    public_url: Optional[str] = None
    document_date: Union[datetime, date, None] = None
    creation_date: Union[datetime, date, None] = None
    updated_date: Union[datetime, date, None] = None
    body_txt: Optional[str] = None
    body_html: Optional[str] = None


def _build(db: Session, rows, include_body: bool, base: str, routes: dict) -> List[dict]:
    """Each page row built by its own list's builder, in the page's order."""
    ids: Dict[str, list] = {}
    for r in rows:
        ids.setdefault(r.src, []).append(int(r.rid))
    built: Dict[tuple, Any] = {}
    for src, rids in ids.items():
        module, table = _BUILDERS[src]
        recs = db.execute(text(f"SELECT {module._DETAIL_COLS} FROM {table} WHERE id = ANY(:ids)"), {"ids": rids}).mappings().all()
        built.update({(src, int(r["id"])): module._row_to_item(r, with_body=include_body) for r in recs})
    out = []
    for r in rows:
        item = built.get((r.src, int(r.rid)))
        if item is None:      # removed between the page query and the build
            continue
        d = item.model_dump()
        path = routes.get((d["body_code"], d["item_type"]))
        d["self"] = base + path.replace("{row_id}", str(d["id"])) if path else None
        out.append(d)
    return out


_DESC = """**What it does**
The EU budget money Brubru holds by fund, in one list: the 2021-2027 cohesion allocations by programme and allocation category (`/erdf`, `/esf-plus`, `/cohesion-fund`, `/jtf`, `/interreg`, `/emfaf`, `/amif`, `/isf`), the EU Solidarity Fund's disaster cases (`/eusf`) and the CAP funds' payments by Member State (`/eagf`, `/eafrd`).

**When to use it**
"How much EU money goes to this country, by fund?", for example `country=PL&order=amount`, or every fund's largest items at once. To work with one fund and all its own fields, use its list; each item's `self` opens it there. The cohesion indicators (outputs and results, counted in units) are on each fund's `/outcomes` list, not here.

**Input**
`q` (words in the item's text, as each fund's list searches), `item_type` (cohesion_allocation | solidarity_case | cap_payment), `body` (the fund: erdf, esf, cf, jtf, interreg, emfaf, amif, isf, eusf, eagf, eafrd), `programme` (a fund's code or name, e.g. `Regional Development`, or words in a cohesion programme's title), `country` (two letters: the Member State, or a Solidarity Fund case's applicant; EL and GR, UK and GB are the same), `status` (adopted | proposed | accepted | rejected | withdrawn | under_assessment; any other text matches the fund's own word, `source_status`, as a substring), `published_from`/`published_to` (the item's `document_date`; `since`, `until`, `from`, `to` are aliases), `created_from`/`created_to` and `updated_from`/`updated_to` (incremental sync; a bare date as `_to` covers the whole day), `min_amount_eur`/`max_amount_eur`, `order` (amount, the default, the largest first | recent | oldest | updated_asc | updated_desc | created_asc | created_desc), `page`, `limit` (default 50, max 200), `include_body` (default true).

**Try it**
```
GET /api/v2/funding/budgets?country=PL
GET /api/v2/funding/budgets?programme=Just%20Transition&order=amount
GET /api/v2/funding/budgets?updated_from=2026-10-25&order=updated_asc
```

**You get back**
A paginated list. Each item is the item of its own list, field for field (an allocation carries its programme, category and years; a case its disaster and damage; a payment row its fund's figures), with `self` (that list's item). The amounts are different money (planned allocations, grants paid, payments made): add them within one `item_type`. The CAP files' EU-total rows (`ms` TOTAL on `/eagf` and `/eafrd`, the sum of the 27 Member States) are left out, so a sum over this list counts each euro once.

**Data freshness**
As each fund's list: every Sunday from the Commission's Cohesion Open Data platform."""


@router.get("/budgets", response_model=PaginatedResponse[BudgetItem], tags=["v2-funding"],
            summary="The EU budget money by fund: cohesion allocations, Solidarity Fund cases and CAP payments in one list",
            description=_DESC)
async def list_budgets(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
    q: Optional[str] = Query(None, description="Words in the item's text, as each fund's list searches it (a substring)."),
    item_type: Optional[str] = Query(None, description="cohesion_allocation | solidarity_case | cap_payment."),
    body: Optional[str] = Query(None, description="The fund: erdf, esf, cf, jtf, interreg, emfaf, amif, isf, eusf, eagf or eafrd."),
    programme: Optional[str] = Query(None, description="A fund's code or name (ERDF, Regional Development), or words in a cohesion programme's title."),
    country: Optional[str] = Query(None, min_length=2, max_length=2, description="Two letters (EL and GR, UK and GB are the same): the Member State, or a Solidarity Fund case's applicant."),
    status: Optional[str] = Query(None, description="adopted | proposed | accepted | rejected | withdrawn | under_assessment (the standard words); any other text matches the fund's own word (`source_status`) as a substring. CAP payment rows have none."),
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
    order: str = Query("amount", description="amount (the largest amount_eur first, the default, as on each fund's list) | recent | oldest | updated_asc | updated_desc | created_asc | created_desc. Page an incremental window with updated_asc."),
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
        params["q"] = f"%{q.strip()}%"
    if item_type:
        where.append("item_type = :item_type"); params["item_type"] = item_type
    if body:
        where.append("body_code = :body"); params["body"] = body.strip().lower()
    if programme and programme.strip():
        funds = _funds_named(programme)
        where.append("(programme_title ILIKE :programme" + (" OR body_code = ANY(:programme_funds))" if funds else ")"))
        params["programme"] = f"%{programme.strip()}%"
        if funds:
            params["programme_funds"] = funds
    if country:
        where.append("upper(country) = ANY(:countries)"); params["countries"] = both_styles(country)
    if status and status.strip():
        if status.strip().lower() in BUDGET_STATUSES:
            where.append("status = :status"); params["status"] = status.strip().lower()
        else:
            where.append("source_status ILIKE :source_status"); params["source_status"] = f"%{status.strip()}%"
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
    union = _union("q" in params)
    rows = db.execute(text(f"SELECT src, rid FROM ({union}) b{clause} ORDER BY {_order_sql(order)} "
                           "LIMIT :limit OFFSET :offset"), params).fetchall()
    total = db.execute(text(f"SELECT count(*) FROM ({union}) b{clause}"), params).scalar() or 0
    data = _build(db, rows, include_body, str(request.base_url).rstrip("/"), _item_routes(request.app))
    return build_envelope(data, total, page, limit,
                          updated_from=window["updated_from"], updated_to=window["updated_to"])
