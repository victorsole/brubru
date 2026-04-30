"""
/api/v1/webstreams — EP webstreams (multimedia.europarl.europa.eu).

Exposes every committee meeting webstream URL discovered by the
sync_committee_transcripts.py scraper. Each row carries:
- multimedia_url: the multimedia.europarl.europa.eu landing page
- video_url: direct stream URL when extracted
- meeting_date + committee_code
- transcript_text (if Whisper has run)

Partners can use this to build per-committee streaming dashboards.
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.committee_meeting_transcript import CommitteeMeetingTranscript
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webstreams", tags=["v1-webstreams"])


class WebstreamItem(BaseModel):
    id: str
    committee_code: str
    title: str
    meeting_date: Optional[datetime] = None
    multimedia_url: Optional[str] = None
    video_url: Optional[str] = None
    event_id: Optional[str] = None
    language: Optional[str] = None
    duration_seconds: Optional[int] = None
    speaker_count: Optional[int] = None
    word_count: Optional[int] = None
    status: Optional[str] = None  # PENDING | COMPLETED | FAILED | NOT_AVAILABLE
    related_procedure_refs: list = Field(default_factory=list)
    transcribed_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None


def _row_to_item(r: CommitteeMeetingTranscript) -> WebstreamItem:
    return WebstreamItem(
        id=str(r.id),
        committee_code=r.committee_code,
        title=r.title or "",
        meeting_date=r.meeting_date,
        multimedia_url=r.multimedia_url,
        video_url=r.video_url,
        event_id=r.event_id,
        language=r.language,
        duration_seconds=r.duration_seconds,
        speaker_count=r.speaker_count,
        word_count=r.word_count,
        status=r.status,
        related_procedure_refs=list(r.related_procedure_refs or []),
        transcribed_at=r.transcribed_at,
        last_updated=r.last_updated,
    )


@router.get(
    "",
    response_model=PaginatedResponse[WebstreamItem],
    summary="EP committee webstreams (multimedia.europarl.europa.eu)",
    description=(
        "Every EP committee meeting webstream URL discovered by the daily "
        "scrape of multimedia.europarl.europa.eu/en/webstreaming. Filter "
        "by committee, date range, status (PENDING / COMPLETED / FAILED / "
        "NOT_AVAILABLE), and incremental sync via updated_from. Transcript "
        "text is included when Whisper has been run; otherwise the row "
        "stays as PENDING and the URL is enough for partners to fetch the "
        "stream themselves."
    ),
)
async def list_webstreams(
    request: Request,
    committee: Optional[str] = Query(None, description="EP committee code (LIBE, ENVI, ECON, ...)"),
    status: Optional[str] = Query(None, description="PENDING | COMPLETED | FAILED | NOT_AVAILABLE"),
    has_transcript: Optional[bool] = Query(None, description="If true, only rows with transcript_text"),
    procedure_ref: Optional[str] = Query(None, description="Filter to streams linked to a procedure"),
    q: Optional[str] = Query(None, description="Substring on title"),
    published_from: Optional[date] = Query(None, description="meeting_date >= value"),
    published_to: Optional[date] = Query(None),
    published_end: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    updated_end: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[WebstreamItem]:
    if published_end and published_to and published_end != published_to:
        raise HTTPException(status_code=422, detail={
            "error": f"Conflicting upper-bound parameters: published_to={published_to} and published_end={published_end}.",
            "reason_code": "conflicting_params",
        })
    if published_end and not published_to:
        published_to = published_end
    if updated_end and updated_to and updated_end != updated_to:
        raise HTTPException(status_code=422, detail={
            "error": f"Conflicting upper-bound parameters: updated_to={updated_to} and updated_end={updated_end}.",
            "reason_code": "conflicting_params",
        })
    if updated_end and not updated_to:
        updated_to = updated_end

    query = db.query(CommitteeMeetingTranscript)
    filters = []
    if committee:
        filters.append(CommitteeMeetingTranscript.committee_code == committee.upper())
    if status:
        filters.append(CommitteeMeetingTranscript.status == status.upper())
    if has_transcript is True:
        filters.append(CommitteeMeetingTranscript.transcript_text.isnot(None))
    elif has_transcript is False:
        filters.append(CommitteeMeetingTranscript.transcript_text.is_(None))
    if procedure_ref:
        filters.append(CommitteeMeetingTranscript.related_procedure_refs.any(procedure_ref))
    if published_from:
        filters.append(CommitteeMeetingTranscript.meeting_date >= published_from)
    if published_to:
        filters.append(CommitteeMeetingTranscript.meeting_date <= datetime.combine(published_to, datetime.max.time()))
    if updated_from:
        filters.append(CommitteeMeetingTranscript.last_updated >= updated_from)
    if updated_to:
        filters.append(CommitteeMeetingTranscript.last_updated <= updated_to)
    if q:
        filters.append(CommitteeMeetingTranscript.title.ilike(f"%{q}%"))
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    if updated_from or updated_to:
        order_col = CommitteeMeetingTranscript.last_updated.desc().nullslast()
    else:
        order_col = CommitteeMeetingTranscript.meeting_date.desc().nullslast()
    rows = query.order_by(order_col).offset((page - 1) * limit).limit(limit).all()

    return build_envelope(
        [_row_to_item(r) for r in rows],
        total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        updated_from=updated_from, updated_to=updated_to,
    )


@router.get(
    "/{stream_id}",
    response_model=WebstreamItem,
    summary="Single webstream by id",
)
async def get_webstream_detail(
    stream_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> WebstreamItem:
    r = db.query(CommitteeMeetingTranscript).filter(CommitteeMeetingTranscript.id == stream_id).first()
    if not r:
        raise HTTPException(status_code=404, detail={
            "error": f"Webstream id={stream_id} not found",
            "reason_code": "not_found",
            "resource": "webstream",
            "id": stream_id,
        })
    return _row_to_item(r)


@router.get(
    "/by-procedure/{procedure_ref:path}/transcript",
    response_model=PaginatedResponse[WebstreamItem],
    summary="Webstreams linked to a specific procedure",
    description=(
        "All webstreams whose related_procedure_refs array includes the given "
        "OEIL reference. Useful for tracking every committee debate of a "
        "specific legislative file."
    ),
)
async def get_webstreams_for_procedure(
    procedure_ref: str,
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[WebstreamItem]:
    query = db.query(CommitteeMeetingTranscript).filter(
        CommitteeMeetingTranscript.related_procedure_refs.any(procedure_ref)
    )
    total = query.count()
    rows = query.order_by(CommitteeMeetingTranscript.meeting_date.desc()).offset((page - 1) * limit).limit(limit).all()
    return build_envelope([_row_to_item(r) for r in rows], total=total, page=page, limit=limit)
