"""GET /api/v2/funding/international-cooperation — EU external-action awards.

The award (recipient) side of EU international cooperation, drawn from the data
Brubru already holds in the EU Financial Transparency System (FTS) — every
commitment under the three external-action instruments:

    NDICI - Global Europe   (programme 6.0.111)   ~11.9k awards
    IPA III                 (programme 6.0.21)    ~2.3k  awards
    Humanitarian Aid (HUMA) (programme 6.0.12)    ~1.3k  awards

Each FTS record is parsed into structured fields — beneficiary, EU amount,
funding_type (grant / procurement contract / contribution), responsible DG,
beneficiary country, contract reference and year — so the feed answers "who won
EU aid money, where, under which instrument, grant or service contract". This is
the market-intelligence side; open biddable tenders run through OPSYS/TED and are
not held here. Backed by economy_items (body_code 'commission', item_type
'funding_recipient'); no new ingestion — the FTS dataset is already synced.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope

router = APIRouter()

# programme key -> (FTS programme-string fragment used for filtering, display label)
_PROGRAMMES = {
    "ndici":        ("Neighbourhood, Development and International", "NDICI - Global Europe"),
    "ipa3":         ("Pre-Accession Assistance (IPA III)",          "IPA III"),
    "humanitarian": ("Humanitarian Aid (HUMA)",                     "Humanitarian Aid"),
}
_ALL_FRAGMENTS = [v[0] for v in _PROGRAMMES.values()]

_ORDERS = {"recent", "oldest", "year"}
_ORDER_SQL = {
    "recent": "document_date DESC NULLS LAST, id DESC",
    "oldest": "document_date ASC NULLS LAST, id ASC",
    "year": "document_date DESC NULLS LAST, id DESC",
}


class _DataPoints(BaseModel):
    public_url: Optional[str] = Field(None, description="Canonical URL (FTS).")
    body_txt: Optional[str] = Field(None, description="Plain-text body (full on detail; null on list).")
    body_html: Optional[str] = Field(None, description="HTML body (full on detail; null on list).")
    document_date: Optional[datetime] = Field(None, description="FTS record date.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru ingested it.")


class IntlCoopItem(_DataPoints):
    id: int
    beneficiary: Optional[str] = Field(None, description="Who received the money.")
    country: Optional[str] = Field(None, description="Beneficiary country.")
    amount_eur: Optional[float] = Field(None, description="EU commitment (total), EUR.")
    funding_type: Optional[str] = Field(None, description="Grant | Procurement contract | Contribution agreement.")
    programme: Optional[str] = Field(None, description="Full FTS programme string.")
    programme_key: Optional[str] = Field(None, description="ndici | ipa3 | humanitarian.")
    dg: Optional[str] = Field(None, description="Responsible Commission department (DG).")
    contract_ref: Optional[str] = Field(None, description="Legal commitment reference.")
    year: Optional[int] = Field(None, description="FTS budget year.")
    subject: Optional[str] = Field(None, description="What the money was for.")


def _field(body: str, label: str) -> Optional[str]:
    m = re.search(rf"{re.escape(label)}:\s*(.+)", body or "")
    return m.group(1).strip() if m else None


def _programme_key(programme: Optional[str]) -> Optional[str]:
    if not programme:
        return None
    for key, (frag, _) in _PROGRAMMES.items():
        if frag.lower() in programme.lower():
            return key
    return None


def _parse(r, *, with_body: bool) -> IntlCoopItem:
    body = r.body_txt or ""
    amount = None
    raw = _field(body, "EU commitment (total)")
    if raw:
        m = re.search(r"([\d.,]+)", raw.replace("EUR", "").strip())
        if m:
            try:
                amount = float(m.group(1).replace(",", ""))
            except ValueError:
                amount = None
    year = _field(body, "Year")
    try:
        year_i = int(year) if year else None
    except ValueError:
        year_i = None
    programme = _field(body, "Programme")
    return IntlCoopItem(
        id=r.id,
        beneficiary=_field(body, "Beneficiary"),
        country=_field(body, "Beneficiary country"),
        amount_eur=amount,
        funding_type=_field(body, "Funding type"),
        programme=programme,
        programme_key=_programme_key(programme),
        dg=_field(body, "Responsible department"),
        contract_ref=_field(body, "Legal commitment ref"),
        year=year_i,
        subject=_field(body, "Subject"),
        public_url=r.public_url,
        body_txt=(r.body_txt if with_body else None),
        body_html=(r.body_html if with_body else None),
        document_date=r.document_date,
        creation_date=r.creation_date,
    )


_BASE = ("FROM economy_items WHERE body_code='commission' AND item_type='funding_recipient'")
_COLS = "id, public_url, body_txt, body_html, document_date, creation_date"

_DESC = """**What it does**
The award (recipient) side of **EU international cooperation** — who received EU money under the three external-action instruments, parsed into structured fields:
- **NDICI - Global Europe** (`programme=ndici`) — ~11.9k awards
- **IPA III** pre-accession (`programme=ipa3`) — ~2.3k awards
- **Humanitarian Aid** (`programme=humanitarian`) — ~1.3k awards

Each item carries `beneficiary`, `country`, `amount_eur`, `funding_type` (grant / procurement contract / contribution), `programme`, `dg`, `contract_ref`, `year` and `subject`.

**When to use it**
Market & competitive intelligence for the EU external-action market: which organisations win EU aid money, in which countries, under which instrument, as grants or service contracts. `funding_type=Procurement contract` isolates technical-assistance service contracts; `country=Türkiye` gives the geographic view.

**Input**
`programme` (ndici | ipa3 | humanitarian), `funding_type` (substring, e.g. `Grant`, `Procurement`), `country` (substring), `year`, `q` (free text), `order` (recent | oldest | year), `page`, `limit`.

**Try it**
```
GET /api/v2/funding/international-cooperation?programme=ipa3&funding_type=Procurement
GET /api/v2/funding/international-cooperation?country=Ukraine
```

**You get back**
A paginated envelope. Each item carries the structured award fields + the 5 datapoints (`body_txt` / `body_html` null on the list — fetch the detail endpoint for the full FTS record).

**Note**
This is the *awards* side (who already received funding). Open biddable tenders run through OPSYS/TED and are not held here.

**Data freshness**
From the EU Financial Transparency System (FTS) annual dataset (most recent complete year)."""


@router.get("/international-cooperation", response_model=PaginatedResponse[IntlCoopItem],
            tags=["v2-funding"],
            summary="EU international cooperation awards — NDICI, IPA III, Humanitarian (who won what, where)",
            description=_DESC)
async def list_intl_cooperation(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
    programme: Optional[str] = Query(None, description="ndici | ipa3 | humanitarian"),
    funding_type: Optional[str] = Query(None, description="Substring, e.g. Grant | Procurement | Contribution."),
    country: Optional[str] = Query(None, description="Beneficiary country substring."),
    year: Optional[int] = Query(None, description="FTS budget year, e.g. 2024."),
    q: Optional[str] = Query(None, description="Free text over beneficiary, subject, programme."),
    order: str = Query("recent", description="recent | oldest | year."),
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
    where = [_BASE.replace("FROM economy_items WHERE ", "")]
    params: dict = {"limit": limit, "offset": (page - 1) * limit}
    if programme:
        if programme not in _PROGRAMMES:
            raise HTTPException(status_code=400, detail=f"programme must be one of {sorted(_PROGRAMMES)}")
        where.append("body_txt ILIKE :prog")
        params["prog"] = f"%{_PROGRAMMES[programme][0]}%"
    else:
        where.append("(" + " OR ".join(f"body_txt ILIKE :f{i}" for i in range(len(_ALL_FRAGMENTS))) + ")")
        for i, frag in enumerate(_ALL_FRAGMENTS):
            params[f"f{i}"] = f"%{frag}%"
    if funding_type:
        where.append("body_txt ILIKE :ft"); params["ft"] = f"%Funding type: %{funding_type}%"
    if country:
        where.append("body_txt ILIKE :ctry"); params["ctry"] = f"%Beneficiary country: %{country}%"
    if year:
        where.append("body_txt ILIKE :yr"); params["yr"] = f"%Year: {year}%"
    if q:
        where.append("(title ILIKE :q OR body_txt ILIKE :q)"); params["q"] = f"%{q}%"
    clause = " AND ".join(where)
    total = db.execute(text(f"SELECT count(*) FROM economy_items WHERE {clause}"), params).scalar() or 0
    rows = db.execute(
        text(f"SELECT {_COLS} FROM economy_items WHERE {clause} "
             f"ORDER BY {_ORDER_SQL[order]} LIMIT :limit OFFSET :offset"), params
    ).fetchall()
    return build_envelope([_parse(r, with_body=include_body) for r in rows], total, page, limit)


@router.get("/international-cooperation/{item_id}", response_model=IntlCoopItem, tags=["v2-funding"],
            summary="One EU international-cooperation award (full FTS record)",
            description="""**What it does**
Returns one EU external-action award in full, including the complete FTS `body_txt` / `body_html` and all parsed fields.

**Input**
`item_id` — the Brubru item id from the list endpoint.

**Try it**
```
GET /api/v2/funding/international-cooperation/{item_id}
```

**You get back**
A single award with the structured fields + the full 5-datapoint contract.

**Data freshness**
From the EU Financial Transparency System (FTS).""")
async def get_intl_cooperation(
    request: Request,
    item_id: int = PathParam(..., description="Brubru item id from the list endpoint."),
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
):
    r = db.execute(
        text(f"SELECT {_COLS} FROM economy_items "
             "WHERE id = :id AND body_code='commission' AND item_type='funding_recipient'"),
        {"id": item_id},
    ).fetchone()
    if r is None:
        raise HTTPException(status_code=404, detail=f"No international-cooperation award with id {item_id}")
    return _parse(r, with_body=True)
