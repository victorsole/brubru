"""
/api/v1/who-is-who/* — the EU interinstitutional directory (Who is Who).

Backed by ``who_is_who_departments`` + ``who_is_who_officials`` (migration 113),
ingested by ``scripts/sync_who_is_who.py`` from the EU SPARQL endpoint.

    /who-is-who/departments  organisational units (DGs, directorates, units) across the EU
    /who-is-who/officials    named officials (name + position + department)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.who_is_who import WhoIsWhoDepartment, WhoIsWhoOfficial
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

departments_router = APIRouter(prefix="/who-is-who/departments", tags=["v1-who-is-who-departments"])
officials_router = APIRouter(prefix="/who-is-who/officials", tags=["v1-who-is-who-officials"])


def _DESC(what, when, inp, gives, example) -> str:
    return f"""**What it does**
{what}

**When to use it**
{when}

**Input**
{inp}

**Try it**
```
{example}
```

**You get back**
{gives} The five envelope datapoints are filled (`public_url` = the Who is Who page, `body_txt`/`body_html` composed, `document_date` = null, `creation_date`).

**Data freshness**
Synced from the EU SPARQL endpoint (the structured EU Whoiswho directory). Bodies composed at ingest."""


class WhoIsWhoDepartmentItem(BaseModel):
    id: str
    mnemonic: Optional[str] = None
    name: str
    institution_uri: Optional[str] = None
    official_count: int = 0
    public_url: Optional[str] = None
    body_txt: Optional[str] = None
    body_html: Optional[str] = None
    document_date: Optional[date] = None
    creation_date: Optional[datetime] = None


class WhoIsWhoOfficialItem(BaseModel):
    id: str
    name: str
    honorific: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    mnemonic: Optional[str] = None
    institution_uri: Optional[str] = None
    person_uri: Optional[str] = None
    public_url: Optional[str] = None
    body_txt: Optional[str] = None
    body_html: Optional[str] = None
    document_date: Optional[date] = None
    creation_date: Optional[datetime] = None


def _to_dept(r: WhoIsWhoDepartment) -> WhoIsWhoDepartmentItem:
    return WhoIsWhoDepartmentItem(
        id=str(r.id), mnemonic=r.mnemonic, name=r.name, institution_uri=r.institution_uri,
        official_count=r.official_count or 0, public_url=r.public_url,
        body_txt=r.body_txt, body_html=r.body_html, document_date=None, creation_date=r.first_seen)


def _to_official(r: WhoIsWhoOfficial) -> WhoIsWhoOfficialItem:
    return WhoIsWhoOfficialItem(
        id=str(r.id), name=r.name, honorific=r.honorific, position=r.position,
        department=r.department, mnemonic=r.mnemonic, institution_uri=r.institution_uri,
        person_uri=r.person_uri, public_url=r.public_url,
        body_txt=r.body_txt, body_html=r.body_html, document_date=None, creation_date=r.first_seen)


@departments_router.get(
    "",
    response_model=PaginatedResponse[WhoIsWhoDepartmentItem],
    summary="EU departments — organisational units across all EU institutions",
    description=_DESC(
        "Returns the organisational units of the EU institutions — Directorates-General, directorates, units, cabinets, services — from the official interinstitutional directory, each with its code and the number of officials listed.",
        "To map the EU's organisational structure, resolve a department code, or find which unit owns a policy area.",
        "- `q` — substring search over department name / code.\n- `mnemonic` — exact department code (e.g. AGRI).\n- `limit` (default 25, max 100), `page`.",
        "A `PaginatedResponse[WhoIsWhoDepartmentItem]`.",
        "GET /api/v1/who-is-who/departments?q=agriculture",
    ),
)
async def list_departments(
    request: Request,
    q: Optional[str] = Query(None),
    mnemonic: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[WhoIsWhoDepartmentItem]:
    query = db.query(WhoIsWhoDepartment)
    f = []
    if q:
        like = f"%{q}%"
        f.append(or_(WhoIsWhoDepartment.name.ilike(like), WhoIsWhoDepartment.mnemonic.ilike(like)))
    if mnemonic:
        f.append(WhoIsWhoDepartment.mnemonic == mnemonic.upper())
    if f:
        query = query.filter(and_(*f))
    total = query.count()
    rows = query.order_by(WhoIsWhoDepartment.official_count.desc().nullslast(),
                          WhoIsWhoDepartment.name).offset((page - 1) * limit).limit(limit).all()
    return build_envelope([_to_dept(r) for r in rows], total=total, page=page, limit=limit,
                          op_core_title="EU departments", op_core_type="EU department",
                          op_core_identifier=str(request.url))


@departments_router.get(
    "/{item_id}",
    response_model=WhoIsWhoDepartmentItem,
    summary="One EU department by id",
    description="Fetch a single EU department by its Brubru UUID. 404 with `reason_code: not_found` if absent.",
)
async def get_department(item_id: str, user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db)) -> WhoIsWhoDepartmentItem:
    row = db.query(WhoIsWhoDepartment).filter(WhoIsWhoDepartment.id == item_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"reason_code": "not_found", "message": f"No department with id {item_id}"})
    return _to_dept(row)


@officials_router.get(
    "",
    response_model=PaginatedResponse[WhoIsWhoOfficialItem],
    summary="EU officials — named officials with position and department",
    description=_DESC(
        "Returns named EU officials from the official interinstitutional directory — each with their position (job title) and the department they belong to, across all EU institutions.",
        "To find who holds a position (e.g. the Director-General of a DG), or to list the officials of a department.",
        "- `q` — substring search over the official's name.\n- `department` — substring match on the department name.\n- `mnemonic` — exact department code.\n- `position` — substring match on the position / job title.\n- `limit` (default 25, max 100), `page`.",
        "A `PaginatedResponse[WhoIsWhoOfficialItem]`.",
        "GET /api/v1/who-is-who/officials?position=Director-General&mnemonic=AGRI",
    ),
)
async def list_officials(
    request: Request,
    q: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    mnemonic: Optional[str] = Query(None),
    position: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[WhoIsWhoOfficialItem]:
    query = db.query(WhoIsWhoOfficial)
    f = []
    if q:
        f.append(WhoIsWhoOfficial.name.ilike(f"%{q}%"))
    if department:
        f.append(WhoIsWhoOfficial.department.ilike(f"%{department}%"))
    if mnemonic:
        f.append(WhoIsWhoOfficial.mnemonic == mnemonic.upper())
    if position:
        f.append(WhoIsWhoOfficial.position.ilike(f"%{position}%"))
    if f:
        query = query.filter(and_(*f))
    total = query.count()
    rows = query.order_by(WhoIsWhoOfficial.name).offset((page - 1) * limit).limit(limit).all()
    return build_envelope([_to_official(r) for r in rows], total=total, page=page, limit=limit,
                          op_core_title="EU officials", op_core_type="EU official",
                          op_core_identifier=str(request.url))


@officials_router.get(
    "/{item_id}",
    response_model=WhoIsWhoOfficialItem,
    summary="One EU official by id",
    description="Fetch a single EU official by its Brubru UUID. 404 with `reason_code: not_found` if absent.",
)
async def get_official(item_id: str, user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db)) -> WhoIsWhoOfficialItem:
    row = db.query(WhoIsWhoOfficial).filter(WhoIsWhoOfficial.id == item_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"reason_code": "not_found", "message": f"No official with id {item_id}"})
    return _to_official(row)
