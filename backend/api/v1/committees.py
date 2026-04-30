"""
/api/v1/committees/* — EP committee work items, minutes, and roster.
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.committee_minutes import CommitteeMinutes
from models.committee_work import CommitteeWorkItem
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

router = APIRouter(prefix="/committees", tags=["v1-committees"])


def _committee_streaming_url(code: str) -> str:
    return f"https://multimedia.europarl.europa.eu/en/webstreaming?committee={code.upper()}"


def _committee_homepage_url(code: str) -> str:
    return f"https://www.europarl.europa.eu/committees/en/{code.lower()}/home/highlights"


def _committee_documents_url(code: str) -> str:
    return f"https://www.europarl.europa.eu/committees/en/{code.lower()}/documents/latest-documents"


class CommitteeWorkEnvelope(PaginatedResponse["CommitteeWorkOut"]):
    committee_code: str
    streaming_url: str
    homepage: str
    documents_url: str


class CommitteeMinutesEnvelope(PaginatedResponse["CommitteeMinutesOut"]):
    committee_code: str
    streaming_url: str
    homepage: str
    documents_url: str


class CommitteeWorkOut(BaseModel):
    id: str
    procedure_ref: Optional[str] = None
    committee_code: str
    title: Optional[str] = None
    procedure_type: Optional[str] = None
    committee_role: Optional[str] = None
    rapporteur_name: Optional[str] = None
    rapporteur_mep_id: Optional[str] = None
    status: Optional[str] = None
    stage: Optional[str] = None
    vote_date: Optional[datetime] = None
    vote_result: Optional[str] = None
    celex_numbers: list = Field(default_factory=list)
    relevance_score: Optional[int] = None


class CommitteeMinutesOut(BaseModel):
    id: str
    committee_code: str
    meeting_date: datetime
    title: str
    pe_reference: Optional[str] = None
    document_reference: Optional[str] = None
    pdf_url: Optional[str] = None
    agenda_items: list = Field(default_factory=list)
    votes: list = Field(default_factory=list)
    decisions: list = Field(default_factory=list)
    attendees_count: Optional[int] = None
    has_full_text: bool = False


@router.get(
    "/{code}/work-items",
    response_model=CommitteeWorkEnvelope,
    summary="Work items tracked by an EP committee",
)
async def list_committee_work(
    request: Request,
    code: str,
    q: Optional[str] = Query(None, description="Substring on title"),
    status: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CommitteeWorkEnvelope:
    query = db.query(CommitteeWorkItem).filter(func.upper(CommitteeWorkItem.committee_code) == code.upper())
    if q:
        query = query.filter(CommitteeWorkItem.title.ilike(f"%{q}%"))
    if status:
        query = query.filter(func.lower(func.cast(CommitteeWorkItem.status, func.TEXT.type)) == status.lower())  # type: ignore
    if stage:
        query = query.filter(func.lower(CommitteeWorkItem.stage) == stage.lower())

    total = query.count()
    rows = query.order_by(CommitteeWorkItem.vote_date.desc().nullslast()).offset((page - 1) * limit).limit(limit).all()
    data = [
        CommitteeWorkOut(
            id=str(r.id),
            procedure_ref=r.procedure_ref,
            committee_code=r.committee_code,
            title=r.title,
            procedure_type=str(r.procedure_type) if r.procedure_type else None,
            committee_role=str(r.committee_role) if r.committee_role else None,
            rapporteur_name=r.rapporteur_name,
            rapporteur_mep_id=r.rapporteur_mep_id,
            status=str(r.status) if r.status else None,
            stage=r.stage,
            vote_date=r.vote_date,
            vote_result=r.vote_result,
            celex_numbers=list(r.celex_numbers or []),
            relevance_score=r.relevance_score,
        )
        for r in rows
    ]
    envelope = build_envelope(data, total=total, page=page, limit=limit)
    return CommitteeWorkEnvelope(
        **envelope.model_dump(),
        committee_code=code.upper(),
        streaming_url=_committee_streaming_url(code),
        homepage=_committee_homepage_url(code),
        documents_url=_committee_documents_url(code),
    )


@router.get(
    "/{code}/minutes",
    response_model=CommitteeMinutesEnvelope,
    summary="Minutes of a committee's meetings",
)
async def list_committee_minutes(
    request: Request,
    code: str,
    published_from: Optional[date] = Query(None, alias="date_from"),
    published_to: Optional[date] = Query(None, alias="date_to"),
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CommitteeMinutesEnvelope:
    query = db.query(CommitteeMinutes).filter(func.upper(CommitteeMinutes.committee_code) == code.upper())
    if published_from:
        query = query.filter(CommitteeMinutes.meeting_date >= published_from)
    if published_to:
        query = query.filter(CommitteeMinutes.meeting_date <= datetime.combine(published_to, datetime.max.time()))
    total = query.count()
    rows = query.order_by(CommitteeMinutes.meeting_date.desc()).offset((page - 1) * limit).limit(limit).all()
    data = [
        CommitteeMinutesOut(
            id=str(r.id),
            committee_code=r.committee_code,
            meeting_date=r.meeting_date,
            title=r.title,
            pe_reference=r.pe_reference,
            document_reference=r.document_reference,
            pdf_url=r.pdf_url,
            agenda_items=list(r.agenda_items or []),
            votes=list(r.votes or []),
            decisions=list(r.decisions or []),
            attendees_count=r.attendees_count,
            has_full_text=bool(r.has_full_text),
        )
        for r in rows
    ]
    envelope = build_envelope(data, total=total, page=page, limit=limit, published_from=published_from, published_to=published_to)
    return CommitteeMinutesEnvelope(
        **envelope.model_dump(),
        committee_code=code.upper(),
        streaming_url=_committee_streaming_url(code),
        homepage=_committee_homepage_url(code),
        documents_url=_committee_documents_url(code),
    )
