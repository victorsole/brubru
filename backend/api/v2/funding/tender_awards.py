"""GET /api/v2/funding/tender-awards — who won the contracts EU institutions, bodies and agencies awarded.

Phase 1 C of the funding standard (proposal 23 Oct 2026, §3.3 and §6, item type `tender_award`). On
21 Oct a partner search for a DG CNECT tender was answered by TED's contract award notices, queried
at TED: Brubru held 104 result notices and no winner. ted_award_notices + ted_award_winners
(migration 315, scripts/sync_ted_awards.py) hold every eForms award notice since 1 Jan 2024 whose
buyer has an EU-body address, with its winners read from the notice's XML.

Field names follow the `tender` item of the standard (contracting_authority, buyer_country,
contract_nature, procedure_type, cpv_main, cpv_codes, lot_count) plus `organisations` (the winners,
role contractor) and `awarded_value` (the notice's total value as stated, in its currency).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.v1._change_window import SYNC_ORDERS, SYNC_PARAMS_DOC, UpperBoundDatetime, sql_order, sql_window, validate_window
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope
from core.database import get_db
from models.user import User
from api.v2.funding.partners import AWARD_WINNER_IS_ORGANISATION
from services.funding.countries import eu_code
from services.funding.shared_fields import AMOUNT_EUR_RULE, amount_eur_sql, cut_summary

router = APIRouter()

# The awarded value in euros (amount_eur): at the ECB reference rate of the publication day (Phase 2
# step 6). Its filters and the amount order read it too: until 29 Oct 2026 they read awarded_value in
# its own currency, so a value in another currency than the euro was ranked by its raw figure.
_AMOUNT_EUR = amount_eur_sql("n.awarded_value", "n.awarded_value_currency", "n.publication_date")
_ORDERS = {"recent", "oldest", "amount"}
_ORDER_SQL = {
    "recent": "n.publication_date DESC NULLS LAST, n.publication_number DESC",
    "oldest": "n.publication_date ASC NULLS LAST, n.publication_number ASC",
    "amount": f"{_AMOUNT_EUR} DESC NULLS LAST, n.publication_number DESC",
}
_TSV = "to_tsvector('english', coalesce(n.title, '') || ' ' || coalesce(n.description, ''))"
_SLUG = "regexp_replace(lower({n}), '[^[:alnum:]]+', '-', 'g')"
_COLS = ("n.publication_number, n.notice_uuid, n.notice_version, n.procedure_uuid, n.notice_subtype, n.superseded_by, "
         "n.publication_date, n.title, n.description, n.contract_nature, n.procedure_type, n.cpv_main, n.cpv_codes, "
         "n.body_code, b.name AS body_name, n.contracting_authority, n.buyer_country, n.buyer_legal_type, "
         "n.awarded_value, n.awarded_value_currency, n.lots, n.lot_count, n.winner_count, n.public_url, "
         f"n.first_seen, n.last_updated, {_AMOUNT_EUR} AS amount_eur")
_FROM = "FROM ted_award_notices n LEFT JOIN economy_bodies b ON b.code = n.body_code WHERE true"


class AwardedOrganisation(BaseModel):
    name: str
    role: str = Field("contractor", description="Always contractor: a winner of the award.")
    country: Optional[str] = Field(None, description="EU style code (EL Greece, UK United Kingdom).")
    city: Optional[str] = None
    company_id: Optional[str] = Field(None, description="As the notice gives it: a VAT, register or tax number.")
    vat: Optional[str] = Field(None, description="company_id when it is shaped like its own country's VAT number.")
    size: Optional[str] = Field(None, description="micro | small | medium | sme | large, as the notice states it.")
    lot_id: Optional[str] = None
    lot_title: Optional[str] = None
    rank: Optional[int] = Field(None, description="The tender's rank, in a cascade framework.")
    is_group_lead: bool = Field(False, description="Leads a joint tender.")
    group_size: int = Field(1, description="Members of its tender (1: it tendered alone).")
    tender_value: Optional[float] = Field(None, description="Its tender's value, shared by the members of a joint tender.")
    tender_value_currency: Optional[str] = None
    contract_reference: Optional[str] = None
    contract_title: Optional[str] = None
    contract_date: Optional[date] = Field(None, description="The contract's signature.")
    award_date: Optional[date] = None
    partner: Optional[str] = Field(None, description="This organisation on /api/v2/funding/partners; none for a winner "
                                   "that may be an individual (see that route's Identity section).")


class TenderAwardItem(BaseModel):
    id: str = Field(..., description="The TED publication number, e.g. 351840-2025.")
    item_type: str = "tender_award"
    title: Optional[str] = None
    summary: Optional[str] = Field(None, description="The start of the notice's description, cut at a word end near 300 characters.")
    status: str = Field("closed", description="Always closed: an award notice ends the competition; each lot's result is in `lots`.")
    publication_number: str
    notice_id: Optional[str] = Field(None, description="eForms notice identifier; a change notice keeps it with a higher version.")
    notice_version: Optional[str] = None
    procedure_id: Optional[str] = None
    form_type: str = "result"
    notice_subtype: Optional[str] = None
    superseded_by: Optional[str] = Field(None, description="A later version of this notice, when Brubru holds one.")
    body_code: Optional[str] = Field(None, description="The EU body that bought (economy_bodies), from its web address.")
    body_name: Optional[str] = None
    contracting_authority: Optional[str] = None
    buyer_country: Optional[str] = None
    buyer_legal_type: Optional[str] = Field(None, description="As TED states it (eu-ins-bod-ag, body-pl ...).")
    buyer_level: str = "eu"
    contract_nature: Optional[str] = Field(None, description="services | supplies | works.")
    procedure_type: Optional[str] = None
    cpv_main: Optional[str] = None
    cpv_codes: List[str] = Field(default_factory=list)
    has_lots: bool = False
    lot_count: int = 0
    lots: list = Field(default_factory=list, description="lot_id, title, description, result, tenders_received.")
    awarded_value: Optional[float] = Field(None, description="The notice's total value as stated (BT-161), in awarded_value_currency.")
    awarded_value_currency: Optional[str] = None
    amount_eur: Optional[float] = Field(None, description=f"awarded_value in euros: {AMOUNT_EUR_RULE}.")
    winner_count: int = 0
    organisations: List[AwardedOrganisation] = Field(default_factory=list, description="The winners, role contractor.")
    public_url: str
    body_txt: Optional[str] = None
    body_html: Optional[str] = None
    document_date: Optional[date] = Field(None, description="The notice's publication date.")
    creation_date: Optional[datetime] = None
    updated_date: Optional[datetime] = None


def _winners(db: Session, pubs: List[str], base: str) -> dict:
    if not pubs:
        return {}
    rows = db.execute(text(
        f"""SELECT w.*, m.pic, {_SLUG.format(n='w.name')} AS slug, {AWARD_WINNER_IS_ORGANISATION} AS is_partner
              FROM ted_award_winners w LEFT JOIN funding_org_identities m ON m.vat_key = w.vat_key
             WHERE w.publication_number = ANY(:pubs)
             ORDER BY w.publication_number, w.lot_id NULLS LAST, w.rank NULLS LAST, w.tender_id, w.is_group_lead DESC, w.org_ref"""),
        {"pubs": pubs}).mappings().all()
    out: dict = {}
    for w in rows:
        key = (f"pic:{w['pic']}" if w["pic"] else f"vat:{w['vat_key']}" if w["vat_key"]
               else f"name:{(w['country'] or '').lower()}:{w['slug']}")
        out.setdefault(w["publication_number"], []).append(AwardedOrganisation(
            name=w["name"], country=w["country"], city=w["city"], company_id=w["company_id"], vat=w["vat_key"],
            size=w["size"], lot_id=w["lot_id"], lot_title=w["lot_title"], rank=w["rank"],
            is_group_lead=w["is_group_lead"], group_size=w["group_size"],
            tender_value=float(w["tender_value"]) if w["tender_value"] is not None else None,
            tender_value_currency=w["tender_value_currency"], contract_reference=w["contract_reference"],
            contract_title=w["contract_title"], contract_date=w["contract_date"], award_date=w["award_date"],
            partner=f"{base}/api/v2/funding/partners/{key}" if w["is_partner"] else None))
    return out


def _item(r, winners: list, with_body: bool, body=None) -> TenderAwardItem:
    value = float(r.awarded_value) if r.awarded_value is not None else None
    return TenderAwardItem(
        id=r.publication_number, title=r.title, summary=cut_summary(r.description),
        publication_number=r.publication_number, notice_id=r.notice_uuid, notice_version=r.notice_version,
        procedure_id=r.procedure_uuid, notice_subtype=r.notice_subtype, superseded_by=r.superseded_by,
        body_code=r.body_code, body_name=r.body_name, contracting_authority=r.contracting_authority,
        buyer_country=r.buyer_country, buyer_legal_type=r.buyer_legal_type, contract_nature=r.contract_nature,
        procedure_type=r.procedure_type, cpv_main=r.cpv_main, cpv_codes=list(r.cpv_codes or []),
        has_lots=(r.lot_count or 0) > 0, lot_count=r.lot_count or 0, lots=r.lots or [],
        awarded_value=value, awarded_value_currency=r.awarded_value_currency,
        amount_eur=float(r.amount_eur) if r.amount_eur is not None else None,
        winner_count=r.winner_count or 0, organisations=winners, public_url=r.public_url,
        body_txt=body[0] if with_body and body else None, body_html=body[1] if with_body and body else None,
        document_date=r.publication_date, creation_date=r.first_seen, updated_date=r.last_updated,
    )


_DESC = f"""**What it does**
Who won the contracts EU institutions, bodies and agencies awarded: every contract award notice on TED (Tenders Electronic Daily) since 1 January 2024 whose buyer is an EU body (the Commission and its departments, the Parliament, the agencies, joint undertakings, the EIB...), with **its winners**: name, country, city, company identifier, size, the lot, the tender's value, the contract's reference and signature date. A buyer counts as an EU body when its own web or e-mail address is on europa.eu (or the EIB's, EIF's and a few joint undertakings' domains): TED's own "EU institution" label is not enough, half of the notices it labels come from national buyers.

**When to use it**
"Who wins contracts like this one": the studies DG CNECT bought and from whom, which firms win EEA framework contracts, the competitors on a call for tenders. For one organisation's awards together with its EU grants and payments, follow a winner's `partner` link to `/api/v2/funding/partners`.

**Input**
- `q` — words in the notice's title and description (full text: every word in any form; `"quoted phrase"`, `OR`, `-word`).
- `contracting_authority` — part of the buyer's name (`CNECT`, `Environment Agency`); `body` — the buyer as a Brubru body code (`commission`, `eea`, `frontex`).
- `winner` — part of a winner's name; `winner_country` — a winner's country (ISO-2; EL and GR, UK and GB are the same).
- `buyer_country`, `contract_nature` (services | supplies | works), `procedure_type` (open, restricted, neg-w-call ...), `cpv_code` (a CPV code or its start: `7241` for IT consulting).
- `published_from`, `published_to` (`since`, `until`, `from`, `to` are aliases); `min_amount_eur`, `max_amount_eur` — awarded value in euros (`amount_eur`), at least / at most; `order=amount` ranks on it too. `country` is the same as `buyer_country`. {SYNC_PARAMS_DOC.replace(chr(10), ' ')}
- `include_superseded` — also the earlier versions of changed notices (default false).
- `order` — recent (default) | oldest | amount | updated_asc | updated_desc | created_asc | created_desc. `page`, `limit` (default 50, max 200), `include_body` (default true).

**Try it**
```
GET /api/v2/funding/tender-awards?contracting_authority=CNECT&q=study
GET /api/v2/funding/tender-awards?body=eea&contract_nature=services
GET /api/v2/funding/tender-awards?q=translation&winner_country=ES
```

**You get back**
A paginated envelope. Each item: `id` (the TED publication number), `title`, `summary`, `contracting_authority`, `body_code`, `buyer_country`, `contract_nature`, `procedure_type`, `cpv_main`, `cpv_codes`, `lots` (each lot's result and tenders received), `awarded_value` and its currency (as the notice states it; `amount_eur` in euros: {AMOUNT_EUR_RULE}; for a framework agreement TED's value is usually the framework's maximum, not money paid: payments are on `/api/v2/funding/eu-funding-recipients`), `organisations` (the winners, as TED names them, role `contractor`, each organisation with its `partner` link; a winner that may be an individual has none), `public_url` (the notice on TED), `body_txt` / `body_html` (the notice as text: on the list unless `include_body=false`, and on the item route), `document_date`, `creation_date`, `updated_date`. A joint tender's members are each listed, the lead flagged; a cascade framework lists every ranked contractor.

**Data freshness**
TED's search API and each notice's XML, read every day for the last 14 days of notices."""


@router.get("/tender-awards", response_model=PaginatedResponse[TenderAwardItem], tags=["v2-funding"],
            summary="Tender awards — who won the contracts EU institutions and agencies awarded (TED)",
            description=_DESC)
async def list_tender_awards(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
    q: Optional[str] = Query(None, description="Words in the notice's title and description (full text)."),
    contracting_authority: Optional[str] = Query(None, description="Part of the buyer's name, e.g. CNECT."),
    body: Optional[str] = Query(None, description="The buyer's Brubru body code, e.g. commission, eea."),
    winner: Optional[str] = Query(None, description="Part of a winner's name."),
    winner_country: Optional[str] = Query(None, min_length=2, max_length=2, description="A winner's country, ISO-2."),
    buyer_country: Optional[str] = Query(None, min_length=2, max_length=2, description="The buyer's country, ISO-2."),
    country: Optional[str] = Query(None, min_length=2, max_length=2, description="The same as `buyer_country` (the funding standard's name)."),
    contract_nature: Optional[str] = Query(None, description="services | supplies | works."),
    procedure_type: Optional[str] = Query(None, description="eForms procedure code: open, restricted, neg-w-call ..."),
    cpv_code: Optional[str] = Query(None, description="A CPV code or its start, matched on any of the notice's codes."),
    published_from: Optional[date] = Query(None, description="Published on or after (YYYY-MM-DD)."),
    published_to: Optional[date] = Query(None, description="Published on or before (YYYY-MM-DD)."),
    since: Optional[date] = Query(None, include_in_schema=False),
    until: Optional[date] = Query(None, include_in_schema=False),
    from_: Optional[date] = Query(None, alias="from", include_in_schema=False),
    to: Optional[date] = Query(None, include_in_schema=False),
    min_amount_eur: Optional[float] = Query(None, ge=0, description="Awarded value in euros (amount_eur) at least; a notice whose value has no euro figure is left out."),
    max_amount_eur: Optional[float] = Query(None, ge=0, description="Awarded value in euros (amount_eur) at most; a notice whose value has no euro figure is left out."),
    include_superseded: bool = Query(False, description="Also the earlier versions of changed notices."),
    created_from: Optional[datetime] = Query(None, description="First recorded by Brubru on or after (ISO date or datetime, UTC)."),
    created_to: Optional[UpperBoundDatetime] = Query(None, description="First recorded by Brubru on or before; a bare date covers the whole day."),
    updated_from: Optional[datetime] = Query(None, description="Last changed on or after. The incremental-sync filter."),
    updated_to: Optional[UpperBoundDatetime] = Query(None, description="Last changed on or before; a bare date covers the whole day."),
    order: str = Query("recent", description="recent | oldest | amount | updated_asc | updated_desc | created_asc | created_desc."),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    include_body: bool = Query(True, description="Return body_txt / body_html on every item of the list (default true)."),
):
    if order not in _ORDERS and order not in SYNC_ORDERS:
        raise HTTPException(status_code=400, detail=f"order must be one of {sorted(_ORDERS) + list(SYNC_ORDERS)}")
    window = validate_window(created_from, created_to, updated_from, updated_to)
    where: list = []
    params: dict = {"limit": limit, "offset": (page - 1) * limit}
    if not include_superseded:
        where.append("n.superseded_by IS NULL")
    if q:
        where.append(f"{_TSV} @@ websearch_to_tsquery('english', :q)"); params["q"] = q
    if contracting_authority:
        where.append("n.contracting_authority ILIKE :ca"); params["ca"] = f"%{contracting_authority}%"
    if body:
        where.append("n.body_code = :body"); params["body"] = body.strip().lower()
    if winner or winner_country:
        w_where = []
        if winner:
            w_where.append("w.name ILIKE :winner"); params["winner"] = f"%{winner}%"
        if winner_country:
            w_where.append("w.country = :wc"); params["wc"] = eu_code(winner_country)
        where.append("EXISTS (SELECT 1 FROM ted_award_winners w WHERE w.publication_number = n.publication_number AND "
                     + " AND ".join(w_where) + ")")
    if buyer_country or country:
        where.append("n.buyer_country = :bc"); params["bc"] = eu_code(buyer_country or country)
    if contract_nature:
        where.append("n.contract_nature = :nature"); params["nature"] = contract_nature.strip().lower()
    if procedure_type:
        where.append("n.procedure_type = :proc"); params["proc"] = procedure_type.strip()
    if cpv_code:
        where.append("EXISTS (SELECT 1 FROM unnest(n.cpv_codes) c WHERE c LIKE :cpv)"); params["cpv"] = f"{cpv_code.strip()}%"
    start, end = published_from or since or from_, published_to or until or to
    if start:
        where.append("n.publication_date >= :start"); params["start"] = start
    if end:
        where.append("n.publication_date <= :end"); params["end"] = end
    if min_amount_eur is not None:
        where.append(f"{_AMOUNT_EUR} >= :min_eur"); params["min_eur"] = min_amount_eur
    if max_amount_eur is not None:
        where.append(f"{_AMOUNT_EUR} <= :max_eur"); params["max_eur"] = max_amount_eur
    sql_window(where, params, window, "n.first_seen", "n.last_updated")
    clause = _FROM + "".join(f" AND {w}" for w in where)
    total = db.execute(text(f"SELECT count(*) {clause}"), params).scalar() or 0
    order_sql = sql_order(order, "n.first_seen", "n.last_updated", "n.publication_number") or _ORDER_SQL[order]
    body_cols = ", n.body_txt, n.body_html" if include_body else ""
    rows = db.execute(text(f"SELECT {_COLS}{body_cols} {clause} ORDER BY {order_sql} LIMIT :limit OFFSET :offset"),
                      params).fetchall()
    base = str(request.base_url).rstrip("/")
    winners = _winners(db, [r.publication_number for r in rows], base)
    items = [_item(r, winners.get(r.publication_number, []), include_body,
                   (r.body_txt, r.body_html) if include_body else None) for r in rows]
    return build_envelope(items, total, page, limit, updated_from=window["updated_from"], updated_to=window["updated_to"])


@router.get("/tender-awards/{publication_number}", response_model=TenderAwardItem, tags=["v2-funding"],
            summary="One tender award — the notice, its lots and its winners",
            description="""**What it does**
One contract award notice from `/api/v2/funding/tender-awards` in full: the notice, each lot's result, every winner, and the notice as text.

**When to use it**
After the list, to read one award's whole record, or to open a notice you found on TED.

**Input**
`publication_number` — TED's publication number (each item's `id`; its `self` is this route).

**Try it**
```
GET /api/v2/funding/tender-awards/351840-2025
```

**You get back**
One item with the list's fields, `body_txt` and `body_html` included, or 404 when Brubru does not hold that notice (it holds award notices since 1 January 2024 whose buyer is an EU body).

**Data freshness**
As the list: read every day for the last 14 days of notices.""")
async def get_tender_award(
    request: Request,
    publication_number: str = PathParam(..., description="TED publication number, e.g. 351840-2025."),
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
):
    r = db.execute(text(f"SELECT {_COLS}, n.body_txt, n.body_html {_FROM} AND n.publication_number = :p"),
                   {"p": publication_number.strip()}).fetchone()
    if r is None:
        raise HTTPException(status_code=404, detail=f"No tender award with publication number {publication_number}")
    base = str(request.base_url).rstrip("/")
    winners = _winners(db, [r.publication_number], base)
    return _item(r, winners.get(r.publication_number, []), True, (r.body_txt, r.body_html))
