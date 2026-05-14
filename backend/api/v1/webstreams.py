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
    # 5 mandatory Brubru v1 datapoints.
    public_url: Optional[str] = Field(
        None,
        description="Citizen URL — the multimedia.europarl.europa.eu page for the meeting (alias of multimedia_url).",
    )
    body_txt: Optional[str] = Field(
        None,
        description="Plain-text composition: title + committee + meeting date + duration + speaker count + status + related procedures.",
    )
    body_html: Optional[str] = Field(
        None,
        description="HTML composition of the same fields.",
    )
    document_date: Optional[date] = Field(
        None,
        description="Meeting date (date-only view of meeting_date).",
    )
    creation_date: Optional[datetime] = Field(
        None,
        description="When Brubru last refreshed this row (alias of last_updated).",
    )
    meeting_start_date: Optional[datetime] = Field(
        None,
        description="Canonical meeting-start timestamp (alias of meeting_date) — the v1 contract uses this name for meeting-bearing endpoints.",
    )


def _row_to_item(r: CommitteeMeetingTranscript) -> WebstreamItem:
    import html as _html
    title = r.title or f"{r.committee_code or 'Committee'} meeting"
    lines = [title]
    parts_html = [f"<h2>{_html.escape(title)}</h2>"]
    for k, v in [
        ("Committee", r.committee_code),
        ("Meeting date", r.meeting_date),
        ("Duration", f"{r.duration_seconds // 60} min" if r.duration_seconds else None),
        ("Speakers", r.speaker_count),
        ("Words", r.word_count),
        ("Status", r.status),
        ("Language", r.language),
        ("Procedures", ", ".join(r.related_procedure_refs) if r.related_procedure_refs else None),
        ("Event id", r.event_id),
    ]:
        if v is None or v == "":
            continue
        lines.append(f"{k}: {v}")
        parts_html.append(f"<p><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</p>")
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
        # 5 mandatory datapoints
        public_url=r.multimedia_url,
        body_txt="\n".join(lines),
        body_html="<article>" + "".join(parts_html) + "</article>",
        document_date=r.meeting_date.date() if hasattr(r.meeting_date, "date") and r.meeting_date else None,
        creation_date=r.last_updated,
        meeting_start_date=r.meeting_date,
    )


@router.get(
    "",
    response_model=PaginatedResponse[WebstreamItem],
    summary="EP committee webstreams — meeting URLs + transcripts (multimedia.europarl.europa.eu)",
    description="""**What it does**
Every EP committee meeting webstream URL discovered by Brubru's daily scrape of `multimedia.europarl.europa.eu/en/webstreaming`. Each row carries the multimedia landing-page URL (`public_url`), the direct video URL when extracted, the meeting date, the committee code (LIBE, ENVI, ECON, …), and — when Whisper has run — the transcript metadata (duration, speaker count, word count).

**When to use it**
- Build per-committee streaming dashboards.
- Track which committee meetings already have a Brubru transcript.
- Filter to meetings linked to a specific OEIL procedure file.
- Drive incremental sync with `updated_from`.

**Input**
- `committee` — EP committee code (LIBE, ENVI, ECON, IMCO, …).
- `status` — `PENDING | COMPLETED | FAILED | NOT_AVAILABLE` (transcription status, not the meeting itself).
- `has_transcript` — true to filter to rows with a transcript already extracted.
- `procedure_ref` — OEIL reference (e.g. `2024/0123(COD)`) to filter to meetings discussing that file.
- `q` — substring on title.
- `published_from` / `published_to` — meeting-date range.
- `updated_from` / `updated_to` — incremental sync.
- `limit` (1–100, default 50), `page` (default 1).

**Try it**
```
GET /api/v1/webstreams?committee=LIBE&has_transcript=true
GET /api/v1/webstreams?procedure_ref=2024%2F0123(COD)
GET /api/v1/webstreams?updated_from=2026-05-01
```

**You get back**
Paginated `WebstreamItem` envelope. `public_url` is the meeting's `multimedia.europarl.europa.eu` landing page (real, specific). `meeting_start_date` carries the meeting timestamp. All 5 mandatory v1 datapoints present per row.

**Data freshness**
Synced every 12 hours (02:00 / 14:00 UTC) from EP committee + plenary webstreams (europarl.europa.eu/committees/.../webstreaming). Transcription fires on-demand when chatbot query hits transcript intent.
""",
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
    summary="Single EP committee webstream by id",
    description="""**What it does**
Returns full metadata for one committee-meeting webstream, including the multimedia landing page (`public_url`), direct video URL, meeting date, transcript status, and (when COMPLETED) duration / speaker / word counts.

**Input**
- `stream_id` (path) — `committee_meeting_transcripts.id` (UUID).

**Try it**
```
GET /api/v1/webstreams/{stream_id}
```

**You get back**
A `WebstreamItem` with all 5 mandatory v1 datapoints. Follow `public_url` to view/replay the meeting on multimedia.europarl.europa.eu.

**Data freshness**
Synced every 12 hours (02:00 / 14:00 UTC) from EP committee + plenary webstreams (europarl.europa.eu/committees/.../webstreaming). Transcription fires on-demand when chatbot query hits transcript intent.
""",
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
    summary="Webstreams linked to a specific OEIL procedure file",
    description="""**What it does**
Returns every committee-meeting webstream whose `related_procedure_refs` array contains the given OEIL reference. Useful for tracking every committee debate of a specific legislative file end-to-end.

**Input**
- `procedure_ref` (path) — OEIL reference, e.g. `2024/0123(COD)`.
- `limit` (1–100, default 50), `page` (default 1).

**Try it**
```
GET /api/v1/webstreams/by-procedure/2024%2F0123(COD)/transcript
```

**You get back**
Paginated `WebstreamItem` envelope ordered by meeting_date desc. Each row's `public_url` resolves to the specific multimedia.europarl.europa.eu meeting page. All 5 mandatory v1 datapoints present per row.

**Data freshness**
Synced every 12 hours (02:00 / 14:00 UTC) from EP committee + plenary webstreams (europarl.europa.eu/committees/.../webstreaming). Transcription fires on-demand when chatbot query hits transcript intent.
""",
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
