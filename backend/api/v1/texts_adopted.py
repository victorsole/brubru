"""
/api/v1/texts-adopted — EP plenary adopted texts (resolutions, legislative acts, decisions).
/api/v1/texts-submitted — EP plenary texts submitted (tabled for debate/vote).

Backed by the texts_adopted table populated by texts_adopted_sync_service.
Texts-submitted is a sibling endpoint surfacing rows that have not yet been
adopted (no adoption_date) — useful for partners tracking the plenary pipeline.
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.text_adopted import TextAdopted
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)


texts_adopted_router = APIRouter(prefix="/texts-adopted", tags=["v1-texts-adopted"])
texts_submitted_router = APIRouter(prefix="/texts-submitted", tags=["v1-texts-submitted"])


class TextItem(BaseModel):
    id: str
    ta_reference: str
    title: str
    description: Optional[str] = None
    text_type: Optional[str] = None
    procedure_ref: Optional[str] = None
    parliamentary_term: int = 10
    adoption_date: Optional[datetime] = None
    committees: list = Field(default_factory=list)
    rapporteur_name: Optional[str] = None
    rapporteur_mep_id: Optional[str] = None
    celex_number: Optional[str] = None
    vote_results: Optional[dict] = None
    related_documents: list = Field(default_factory=list)
    source_url: Optional[str] = None
    full_text_url: Optional[str] = None
    pdf_url: Optional[str] = None
    last_updated: Optional[datetime] = None


def _row_to_item(r: TextAdopted) -> TextItem:
    return TextItem(
        id=str(r.id),
        ta_reference=r.ta_reference,
        title=r.title,
        description=r.description,
        text_type=r.text_type.value if hasattr(r.text_type, "value") else (str(r.text_type) if r.text_type else None),
        procedure_ref=r.procedure_ref,
        parliamentary_term=int(r.parliamentary_term or 10),
        adoption_date=r.adoption_date,
        committees=list(r.committees or []),
        rapporteur_name=r.rapporteur_name,
        rapporteur_mep_id=r.rapporteur_mep_id,
        celex_number=r.celex_number,
        vote_results=r.vote_results if isinstance(r.vote_results, dict) else None,
        related_documents=list(r.related_documents or []) if r.related_documents else [],
        source_url=r.source_url,
        full_text_url=r.full_text_url,
        pdf_url=r.pdf_url,
        last_updated=r.last_updated,
    )


def _validate_date_params(
    published_from, published_to, published_end,
    updated_from, updated_to, updated_end,
):
    if published_end and published_to and published_end != published_to:
        raise HTTPException(status_code=422, detail={
            "error": f"Conflicting upper-bound parameters: published_to={published_to} and published_end={published_end}.",
            "reason_code": "conflicting_params",
        })
    if published_end and not published_to:
        published_to = published_end
    if published_from and published_to and published_from > published_to:
        raise HTTPException(status_code=422, detail={
            "error": f"Invalid date range: published_from={published_from} after published_to={published_to}.",
            "reason_code": "invalid_date_range",
        })
    if updated_end and updated_to and updated_end != updated_to:
        raise HTTPException(status_code=422, detail={
            "error": f"Conflicting upper-bound parameters: updated_to={updated_to} and updated_end={updated_end}.",
            "reason_code": "conflicting_params",
        })
    if updated_end and not updated_to:
        updated_to = updated_end
    return published_to, updated_to


@texts_adopted_router.get(
    "",
    response_model=PaginatedResponse[TextItem],
    summary="EP texts adopted (plenary)",
    description=(
        "Resolutions, legislative resolutions, decisions, and recommendations adopted "
        "by the European Parliament in plenary. Filterable by text type, procedure ref, "
        "term, committee, rapporteur, adoption-date, and incremental sync via updated_from."
    ),
)
async def list_texts_adopted(
    request: Request,
    q: Optional[str] = Query(None, description="Substring on title + description"),
    text_type: Optional[str] = Query(None, description="resolution | legislative_resolution | decision | recommendation | other"),
    procedure_ref: Optional[str] = Query(None),
    parliamentary_term: Optional[int] = Query(None, description="EP term, e.g. 9, 10"),
    committee: Optional[str] = Query(None),
    rapporteur_mep_id: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None, description="adoption_date >= value"),
    published_to: Optional[date] = Query(None),
    published_end: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    updated_end: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TextItem]:
    published_to, updated_to = _validate_date_params(
        published_from, published_to, published_end,
        updated_from, updated_to, updated_end,
    )

    query = db.query(TextAdopted).filter(TextAdopted.adoption_date.isnot(None))
    filters = []
    if text_type:
        filters.append(TextAdopted.text_type == text_type.lower())
    if procedure_ref:
        filters.append(TextAdopted.procedure_ref == procedure_ref)
    if parliamentary_term is not None:
        filters.append(TextAdopted.parliamentary_term == parliamentary_term)
    if committee:
        filters.append(TextAdopted.committees.any(committee.upper()))
    if rapporteur_mep_id:
        filters.append(TextAdopted.rapporteur_mep_id == rapporteur_mep_id)
    if published_from:
        filters.append(TextAdopted.adoption_date >= published_from)
    if published_to:
        filters.append(TextAdopted.adoption_date <= datetime.combine(published_to, datetime.max.time()))
    if updated_from:
        filters.append(TextAdopted.last_updated >= updated_from)
    if updated_to:
        filters.append(TextAdopted.last_updated <= updated_to)
    if q:
        like = f"%{q}%"
        filters.append(or_(TextAdopted.title.ilike(like), TextAdopted.description.ilike(like)))
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    if updated_from or updated_to:
        order_col = TextAdopted.last_updated.desc().nullslast()
    else:
        order_col = TextAdopted.adoption_date.desc().nullslast()
    rows = query.order_by(order_col).offset((page - 1) * limit).limit(limit).all()

    return build_envelope(
        [_row_to_item(r) for r in rows],
        total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        updated_from=updated_from, updated_to=updated_to,
    )


@texts_adopted_router.get(
    "/{ta_reference}",
    response_model=TextItem,
    summary="Single adopted text by TA reference (e.g. P10_TA(2025)0042)",
)
async def get_text_adopted_detail(
    ta_reference: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> TextItem:
    r = db.query(TextAdopted).filter(TextAdopted.ta_reference == ta_reference).first()
    if not r:
        raise HTTPException(status_code=404, detail={
            "error": f"TA reference {ta_reference} not found",
            "reason_code": "not_found",
            "resource": "text_adopted",
            "id": ta_reference,
        })
    return _row_to_item(r)


@texts_submitted_router.get(
    "",
    response_model=PaginatedResponse[TextItem],
    summary="EP texts submitted (tabled for plenary, not yet adopted)",
    description=(
        "EP plenary texts that have been tabled but not yet adopted "
        "(no adoption_date). Sibling endpoint to /texts-adopted for partners "
        "tracking the plenary pipeline. Source: europarl.europa.eu/plenary/en/texts-submitted.html"
    ),
)
async def list_texts_submitted(
    request: Request,
    q: Optional[str] = Query(None),
    text_type: Optional[str] = Query(None),
    procedure_ref: Optional[str] = Query(None),
    parliamentary_term: Optional[int] = Query(None),
    committee: Optional[str] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    updated_end: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TextItem]:
    if updated_end and updated_to and updated_end != updated_to:
        raise HTTPException(status_code=422, detail={
            "error": f"Conflicting upper-bound parameters: updated_to={updated_to} and updated_end={updated_end}.",
            "reason_code": "conflicting_params",
        })
    if updated_end and not updated_to:
        updated_to = updated_end

    # Texts-submitted = rows in the same table without an adoption_date yet.
    query = db.query(TextAdopted).filter(TextAdopted.adoption_date.is_(None))
    filters = []
    if text_type:
        filters.append(TextAdopted.text_type == text_type.lower())
    if procedure_ref:
        filters.append(TextAdopted.procedure_ref == procedure_ref)
    if parliamentary_term is not None:
        filters.append(TextAdopted.parliamentary_term == parliamentary_term)
    if committee:
        filters.append(TextAdopted.committees.any(committee.upper()))
    if updated_from:
        filters.append(TextAdopted.last_updated >= updated_from)
    if updated_to:
        filters.append(TextAdopted.last_updated <= updated_to)
    if q:
        like = f"%{q}%"
        filters.append(or_(TextAdopted.title.ilike(like), TextAdopted.description.ilike(like)))
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(TextAdopted.last_updated.desc().nullslast())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return build_envelope(
        [_row_to_item(r) for r in rows],
        total=total, page=page, limit=limit,
        updated_from=updated_from, updated_to=updated_to,
    )
