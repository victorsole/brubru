"""
/api/v1/specialised/comitology — EU Comitology Register documents.

Source API discovered via Playwright network capture:
  https://ec.europa.eu/transparency/comitology-register/core/api/front/

Backed by eu_comitology_documents. ~112,832 documents from
~300 committees overseeing the Commission's implementing acts.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from ._body import body_threshold_param, deprecated_body
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/specialised/comitology", tags=["v1-specialised-ec-databases"])


class ComitologyDocItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    document_reference: str
    title: Optional[str] = None
    meeting_code: Optional[str] = None
    committee_code: Optional[str] = None
    committee_title: Optional[str] = None
    document_type_label: Optional[str] = None
    document_type_letter: Optional[str] = None
    creation_date: Optional[datetime] = None
    meeting_start_date: Optional[datetime] = None
    public_url: Optional[str] = None
    has_body: bool = False


class ComitologyDocDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    document_reference: str
    title: Optional[str] = None
    meeting_code: Optional[str] = None
    committee_code: Optional[str] = None
    committee_title: Optional[str] = None
    document_type: Optional[dict] = None
    document_type_label: Optional[str] = None
    document_type_letter: Optional[str] = None
    creation_date: Optional[datetime] = None
    update_date: Optional[datetime] = None
    meeting_start_date: Optional[datetime] = None
    meeting_end_date: Optional[datetime] = None
    version: Optional[int] = None
    public_url: Optional[str] = None
    has_body: bool = False
    body_html: Optional[str] = None
    body_txt: Optional[str] = None
    body_source: Optional[str] = None
    body: Optional[str] = Field(None, description="DEPRECATED — back-compat alias.")


class CommitteeItem(BaseModel):
    code: str
    title: Optional[str] = None
    dg_code: Optional[str] = None
    dg_title: Optional[str] = None
    parent_code: Optional[str] = None
    abolished_since: Optional[datetime] = None
    public_url: Optional[str] = None


@router.get(
    "/documents",
    response_model=PaginatedResponse[ComitologyDocItem],
    summary="Comitology Register documents (committee meeting outputs)",
    description="""**What it does**
Returns the catalogue of documents from EU comitology committees — the committees of Member State representatives that oversee the Commission's adoption of implementing acts. Includes agendas, summary records, voting sheets, draft implementing acts, urgency letters and other documents. Sourced via the live JSON API at `ec.europa.eu/transparency/comitology-register/core/api/front/`.

**When to use it**
- Trace what a committee voted on and what record it produced.
- Track implementing-act drafts as they progress through comitology.
- Cross-reference Commission proposals with their oversight committees.

**Input**
- `committee` (string, optional) — committee code (e.g. `C20407`).
- `document_type_letter` (string, optional) — A=agenda, D=draft, V=vote, S=summary record, O=other, U=urgency.
- `q` (string, optional) — full-text search on title.
- `meeting_from` / `meeting_to` (dates, optional) — bounds on meeting_start_date.
- `limit` (int, 1–200, default 50), `page` (int, default 1).
- `body_threshold` (int, default 500) — contract parity.

**Try it**
```
GET /api/v1/specialised/comitology/documents?document_type_letter=V&limit=20
```

**You get back**
A paginated envelope of `ComitologyDocItem` rows.""",
)
async def list_documents(
    request: Request,
    committee: Optional[str] = Query(None),
    document_type_letter: Optional[str] = Query(None, regex="^[ADVOSU]$"),
    q: Optional[str] = Query(None),
    meeting_from: Optional[date] = Query(None),
    meeting_to: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ComitologyDocItem]:
    where: list[str] = []
    params: dict = {}
    if committee:
        where.append("committee_code = :committee"); params["committee"] = committee
    if document_type_letter:
        where.append("document_type_letter = :dtl"); params["dtl"] = document_type_letter
    if q:
        where.append("to_tsvector('english', COALESCE(title,'')) @@ plainto_tsquery('english', :q)")
        params["q"] = q
    if meeting_from:
        where.append("meeting_start_date >= :meeting_from"); params["meeting_from"] = meeting_from
    if meeting_to:
        where.append("meeting_start_date <= :meeting_to"); params["meeting_to"] = meeting_to
    where_sql = "WHERE " + " AND ".join(where) if where else ""

    total = int(db.execute(text(f"SELECT COUNT(*) FROM eu_comitology_documents {where_sql}"), params).scalar() or 0)

    offset = (page - 1) * limit
    rows = db.execute(text(f"""
        SELECT document_reference, title, meeting_code, committee_code, committee_title,
               document_type_label, document_type_letter,
               creation_date, meeting_start_date, public_url
          FROM eu_comitology_documents
          {where_sql}
         ORDER BY meeting_start_date DESC NULLS LAST, document_reference DESC
         LIMIT :limit OFFSET :offset
    """), {**params, "limit": limit, "offset": offset}).mappings().all()

    items = [ComitologyDocItem(
        document_reference=r["document_reference"],
        title=r.get("title"),
        meeting_code=r.get("meeting_code"),
        committee_code=r.get("committee_code"),
        committee_title=r.get("committee_title"),
        document_type_label=r.get("document_type_label"),
        document_type_letter=r.get("document_type_letter"),
        creation_date=r.get("creation_date"),
        meeting_start_date=r.get("meeting_start_date"),
        public_url=r.get("public_url"),
        has_body=False,
    ) for r in rows]

    return build_envelope(items=items, total=total, page=page, limit=limit,
        op_core_title="EU Comitology Register documents",
        op_core_type="Comitology document",
        op_core_identifier=str(request.url),
        op_core_referenced_by=["/api/v1/specialised/comitology/documents/{reference}",
                               "/api/v1/specialised/comitology/committees"])


@router.get(
    "/committees",
    response_model=PaginatedResponse[CommitteeItem],
    summary="Comitology committees overseeing implementing acts",
    description="""**What it does**
Returns the list of comitology committees registered in the EU register. Each is identified by a code (e.g. `C20407` for the Phytopharmaceuticals Section of the Standing Committee on Plants, Animals, Food and Feed) and belongs to a Directorate-General.

**When to use it**
- Map which committee oversees which implementing acts.
- Build a committee picker.
- Cross-reference DG attribution.

**Input**
- `dg_code` (string, optional) — e.g. `SANTE`, `ENV`, `ENER`.
- `q` (string, optional) — case-insensitive substring on title.
- `limit` (int, 1–500, default 50), `page` (int, default 1).
- `body_threshold` (int, default 500) — contract parity.

**Try it**
```
GET /api/v1/specialised/comitology/committees?dg_code=SANTE
```

**You get back**
A paginated envelope of `CommitteeItem` rows.""",
)
async def list_committees(
    request: Request,
    dg_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CommitteeItem]:
    where: list[str] = []
    params: dict = {}
    if dg_code:
        where.append("dg_code = :dg_code"); params["dg_code"] = dg_code.upper()
    if q:
        where.append("title ILIKE :q"); params["q"] = f"%{q}%"
    where_sql = "WHERE " + " AND ".join(where) if where else ""

    total = int(db.execute(text(f"SELECT COUNT(*) FROM eu_comitology_committees {where_sql}"), params).scalar() or 0)

    offset = (page - 1) * limit
    rows = db.execute(text(f"""
        SELECT code, title, dg_code, dg_title, parent_code, abolished_since, public_url
          FROM eu_comitology_committees
          {where_sql}
         ORDER BY dg_code, code
         LIMIT :limit OFFSET :offset
    """), {**params, "limit": limit, "offset": offset}).mappings().all()

    items = [CommitteeItem(
        code=r["code"], title=r.get("title"), dg_code=r.get("dg_code"),
        dg_title=r.get("dg_title"), parent_code=r.get("parent_code"),
        abolished_since=r.get("abolished_since"), public_url=r.get("public_url"),
    ) for r in rows]

    return build_envelope(items=items, total=total, page=page, limit=limit,
        op_core_title="EU Comitology committees", op_core_type="Comitology committee",
        op_core_identifier=str(request.url))


@router.get(
    "/documents/{reference}",
    response_model=ComitologyDocDetail,
    summary="Single Comitology document by reference",
    description="""**What it does**
Returns the full record for one comitology document, identified by its document reference (e.g. `115543`).

**Input**
- `reference` (path) — comitology document reference.
- `body_threshold` (int, default 500).

**Try it**
```
GET /api/v1/specialised/comitology/documents/115543
```""",
)
async def get_document(
    request: Request,
    reference: str = Path(..., description="Comitology document reference, e.g. 115543."),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> ComitologyDocDetail:
    row = db.execute(text(
        "SELECT * FROM eu_comitology_documents WHERE document_reference = :ref LIMIT 1"
    ), {"ref": reference}).mappings().first()
    if not row:
        raise HTTPException(status_code=404,
            detail={"error": f"Document '{reference}' not found.", "reason_code": "not_found"})

    body_text = row.get("body_text")
    has_body = bool(body_text and len(body_text) >= body_threshold)

    return ComitologyDocDetail(
        document_reference=row["document_reference"],
        title=row.get("title"),
        meeting_code=row.get("meeting_code"),
        committee_code=row.get("committee_code"),
        committee_title=row.get("committee_title"),
        document_type=row.get("document_type"),
        document_type_label=row.get("document_type_label"),
        document_type_letter=row.get("document_type_letter"),
        creation_date=row.get("creation_date"),
        update_date=row.get("update_date"),
        meeting_start_date=row.get("meeting_start_date"),
        meeting_end_date=row.get("meeting_end_date"),
        version=row.get("version"),
        public_url=row.get("public_url"),
        has_body=has_body,
        body_html=row.get("body_html"),
        body_txt=body_text,
        body_source=row.get("body_source"),
        body=deprecated_body(body_text, row.get("body_html")),
    )
