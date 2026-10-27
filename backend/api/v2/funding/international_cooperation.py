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

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, Request
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from api.v1._change_window import (SYNC_ORDERS, UpperBoundDatetime, any_window, sql_order, sql_window,
                                   validate_window)
from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope

from . import _fts

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
    "recent": "e.document_date DESC NULLS LAST, e.id DESC",
    "oldest": "e.document_date ASC NULLS LAST, e.id ASC",
    "year": "c.year DESC NULLS LAST, e.document_date DESC NULLS LAST, e.id DESC",
}


class IntlCoopItem(_fts.FtsItem):
    programme_key: Optional[str] = Field(None, description="ndici | ipa3 | humanitarian.")


def _programme_key(programme: Optional[str]) -> Optional[str]:
    if not programme:
        return None
    for key, (frag, _) in _PROGRAMMES.items():
        if frag.lower() in programme.lower():
            return key
    return None


def _item(r, *, with_body: bool) -> IntlCoopItem:
    return _fts.to_item(r, with_body=with_body, model=IntlCoopItem, programme_key=_programme_key(r.programme))


# The page itself is an index range (8 ms), but its exact total reads every matching award's
# heap page: 21,224 rows, 15,000 blocks, 4.6 s (20 Oct 2026). The awards change when the yearly
# FTS file is re-read, so a total is kept for 15 minutes per filter combination.
_TOTALS: dict = {}
_TOTAL_TTL_S = 900


def _cached_total(db, clause: str, params: dict) -> int:
    import time
    key = (clause, tuple(sorted((k, str(v)) for k, v in params.items() if k not in ("limit", "offset"))))
    hit = _TOTALS.get(key)
    if hit and time.monotonic() - hit[0] < _TOTAL_TTL_S:
        return hit[1]
    total = db.execute(text(f"SELECT count(*) {clause}"), params).scalar() or 0
    if len(_TOTALS) > 512:
        _TOTALS.clear()
    _TOTALS[key] = (time.monotonic(), total)
    return total

_DESC = """**What it does**
The award (recipient) side of **EU international cooperation** — who received EU money under the three external-action instruments, with the EU Financial Transparency System file's own values (FTS files 2024 and 2025):
- **NDICI - Global Europe** (`programme=ndici`) — 15,708 awards (11,882 in 2024, 3,826 in 2025)
- **IPA III** pre-accession (`programme=ipa3`) — 3,115 (2,295 and 820)
- **Humanitarian Aid** (`programme=humanitarian`) — 2,401 (1,335 and 1,066)

Each item carries `beneficiary`, `country`, `amount_eur` (this beneficiary's contracted amount; until 26 Oct 2026 it was the whole commitment's total, now `commitment_total_eur`), `funding_type` (the FTS type of contract: Action Grant, Contribution Agreements, Budget support, or a procurement category such as Advisory: Studies), `programme`, `programme_key`, `dg`, `contract_ref`, `year`, `subject`, and the other FTS fields of `/api/v2/funding/eu-funding-recipients` (`is_coordinator`, `vat_number`, `project_id`...).

**When to use it**
Market & competitive intelligence for the EU external-action market: which organisations win EU aid money, in which countries, under which instrument, as grants or service contracts. `funding_type=Advisory` isolates the advisory service contracts (studies, evaluations, audits); `country=Türkiye` gives the geographic view.

**Input**
`programme` (ndici | ipa3 | humanitarian), `funding_type` (part of the FTS type of contract, e.g. `Grant`, `Advisory`, `Contribution`), `country` (part of the FTS country name), `year` (2024 | 2025), `q` (words in the record), `order` (recent | oldest | year), `page`, `limit`. `created_from` / `created_to` and `updated_from` / `updated_to` for incremental sync (a bare date as `_to` covers the whole day; a daily re-read that finds the same content does not move `updated_date`), paged with `order=updated_asc`.

**Try it**
```
GET /api/v2/funding/international-cooperation?programme=ipa3&funding_type=Advisory
GET /api/v2/funding/international-cooperation?country=Ukraine
```

**You get back**
A paginated envelope. Each item carries the structured award fields + the 5 datapoints (`body_txt` / `body_html` on every item unless `include_body=false`; the detail endpoint has the full FTS record).

**Note**
This is the *awards* side (who already received funding). Open biddable tenders run through OPSYS/TED and are not held here.

**Data freshness**
The EU Financial Transparency System (FTS) files for 2024 and 2025, read every Sunday with their own columns (commission-heavy tier)."""


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
    created_from: Optional[datetime] = Query(None, description="First recorded by Brubru on or after (ISO date or datetime, UTC)."),
    created_to: Optional[UpperBoundDatetime] = Query(None, description="First recorded by Brubru on or before; a bare date covers the whole day."),
    updated_from: Optional[datetime] = Query(None, description="Content last changed on or after (ISO date or datetime, UTC). The incremental-sync filter."),
    updated_to: Optional[UpperBoundDatetime] = Query(None, description="Content last changed on or before; a bare date covers the whole day."),
    order: str = Query("recent", description="recent | oldest | year | updated_asc | updated_desc | created_asc | created_desc. Page an incremental window with updated_asc."),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    include_body: bool = Query(
        True,
        description=(
            "Return `body_txt` / `body_html` on every item in the list (default true, "
            "the funding standard)."
        ),
    ),
):
    if order not in _ORDERS and order not in SYNC_ORDERS:
        raise HTTPException(status_code=400, detail=f"order must be one of {sorted(_ORDERS) + list(SYNC_ORDERS)}")
    window = validate_window(created_from, created_to, updated_from, updated_to)
    where: list = []
    params: dict = {"limit": limit, "offset": (page - 1) * limit}
    # The programme on the FTS file's own column since 26 Oct 2026 (it was matched on `summary`,
    # whose trigram index kept a body ILIKE from taking 70-77 s, 20 Oct).
    if programme:
        if programme not in _PROGRAMMES:
            raise HTTPException(status_code=400, detail=f"programme must be one of {sorted(_PROGRAMMES)}")
        where.append("c.programme ILIKE :prog")
        params["prog"] = f"%{_PROGRAMMES[programme][0]}%"
    else:
        where.append("(" + " OR ".join(f"c.programme ILIKE :f{i}" for i in range(len(_ALL_FRAGMENTS))) + ")")
        for i, frag in enumerate(_ALL_FRAGMENTS):
            params[f"f{i}"] = f"%{frag}%"
    _fts.filters(where, params, funding_type=funding_type, country=country, year=year)
    if q:
        where.append("e.search_vector @@ plainto_tsquery('english', :q)"); params["q"] = q
    # The change window, on the columns served as creation_date / updated_date.
    sql_window(where, params, window, "e.creation_date", _fts.UPDATED)
    clause = _fts.FROM + "".join(f" AND {w}" for w in where)
    # A change window is counted live: a 15-minute-old total would miss what just changed.
    total = (db.execute(text(f"SELECT count(*) {clause}"), params).scalar() or 0
             if any_window(window) else _cached_total(db, clause, params))
    order_sql = sql_order(order, "e.creation_date", _fts.UPDATED, "e.id") or _ORDER_SQL[order]
    rows = db.execute(text(f"SELECT {_fts.cols(include_body)} {clause} ORDER BY {order_sql} "
                           "LIMIT :limit OFFSET :offset"), params).fetchall()
    return build_envelope([_item(r, with_body=include_body) for r in rows], total, page, limit,
                          updated_from=window["updated_from"], updated_to=window["updated_to"])


@router.get("/international-cooperation/{item_id}", response_model=IntlCoopItem, tags=["v2-funding"],
            summary="One EU international-cooperation award (full FTS record)",
            description="""**What it does**
Returns one EU external-action award in full: the FTS file's own values and the complete `body_txt` / `body_html`.

**Input**
`item_id` — the Brubru item id from the list endpoint.

**Try it**
```
GET /api/v2/funding/international-cooperation?programme=ipa3&limit=1
```
then follow the item's `self`.

**You get back**
A single award with the FTS file's fields + the full 5-datapoint contract, or 404.

**Data freshness**
The FTS files for 2024 and 2025, read every Sunday.""")
async def get_intl_cooperation(
    request: Request,
    item_id: int = PathParam(..., description="Brubru item id from the list endpoint."),
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
):
    r = db.execute(text(f"SELECT {_fts.cols(True)} {_fts.FROM} AND e.id = :id"), {"id": item_id}).fetchone()
    if r is None:
        raise HTTPException(status_code=404, detail=f"No international-cooperation award with id {item_id}")
    return _item(r, with_body=True)
