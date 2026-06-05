"""
/api/v1/general-publications — EU general publications (Publications Office).

Backed by ``eu_general_publications`` (migration 114), ingested by
``scripts/sync_general_publications.py`` from the EU SPARQL endpoint (Cellar
works of resource-type PUB_GEN: brochures, reports, studies).
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from core.database import get_db
from models.general_publication import EuGeneralPublication
from models.user import User
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

router = APIRouter(prefix="/general-publications", tags=["v1-general-publications"])


class GeneralPublicationItem(BaseModel):
    id: str
    publication_id: str
    cellar_uri: Optional[str] = None
    title: str
    public_url: Optional[str] = None
    body_txt: Optional[str] = None
    body_html: Optional[str] = None
    document_date: Optional[date] = Field(None, description="Publication date.")
    creation_date: Optional[datetime] = None


def _to_item(r: EuGeneralPublication) -> GeneralPublicationItem:
    return GeneralPublicationItem(
        id=str(r.id), publication_id=r.publication_id, cellar_uri=r.cellar_uri, title=r.title,
        public_url=r.public_url, body_txt=r.body_txt, body_html=r.body_html,
        document_date=r.publication_date, creation_date=r.first_seen)


@router.get(
    "",
    response_model=PaginatedResponse[GeneralPublicationItem],
    summary="EU general publications — brochures, reports and studies",
    description="""**What it does**
Returns the EU Publications Office's general publications (brochures, reports, studies) — Cellar works of resource-type PUB_GEN — each with its title, publication date, and the read/download page.

**When to use it**
To search the EU's catalogue of general (non-legal) publications across all policy areas.

**Input**
- `q` — substring search over the title.
- `published_from`, `published_to` — bound on the publication date.
- `limit` (default 25, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/general-publications?q=artificial+intelligence
```

**You get back**
A `PaginatedResponse[GeneralPublicationItem]` with the five envelope datapoints filled (`public_url` = the publication page, `body_txt`/`body_html` composed, `document_date` = publication date, `creation_date`).

**Data freshness**
Synced from the EU SPARQL endpoint (Cellar). Bodies composed at ingest."""
)
async def list_general_publications(
    request: Request,
    q: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[GeneralPublicationItem]:
    query = db.query(EuGeneralPublication)
    if q:
        query = query.filter(EuGeneralPublication.title.ilike(f"%{q}%"))
    if published_from:
        query = query.filter(EuGeneralPublication.publication_date >= published_from)
    if published_to:
        query = query.filter(EuGeneralPublication.publication_date <= published_to)
    total = query.count()
    rows = (query.order_by(EuGeneralPublication.publication_date.desc().nullslast())
            .offset((page - 1) * limit).limit(limit).all())
    return build_envelope([_to_item(r) for r in rows], total=total, page=page, limit=limit,
                          published_from=published_from, published_to=published_to,
                          op_core_title="EU general publications", op_core_type="EU publication",
                          op_core_identifier=str(request.url))


@router.get(
    "/{item_id}",
    response_model=GeneralPublicationItem,
    summary="One EU general publication by id",
    description="Fetch a single EU general publication by its Brubru UUID. 404 with `reason_code: not_found` if absent.",
)
async def get_general_publication(item_id: str, user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db)) -> GeneralPublicationItem:
    row = db.query(EuGeneralPublication).filter(EuGeneralPublication.id == item_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"reason_code": "not_found", "message": f"No publication with id {item_id}"})
    return _to_item(row)
