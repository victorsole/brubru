"""
/api/v1/committee-transcripts/* — AI-generated transcripts of EP committee
(and subcommittee) meeting recordings from the EP Multimedia Centre.

Backed by the `committee_meeting_transcripts` table (model
models.committee_meeting_transcript). Each COMPLETED row carries the full
Whisper transcript of a committee meeting webstream, mapped agenda items, and
the procedure references discussed. This is the textual companion to
/api/v1/webstreams (which exposes the stream URL + transcript *status*); this
endpoint exposes the transcript *content*.

The 5 mandatory v1 datapoints are populated from real data only:
    public_url    -> multimedia_url | video_url | committee webstreaming page
    body_txt      -> transcript_text (verbatim Whisper output)
    body_html     -> composed from transcript_segments (one <p> per segment,
                     speaker label when present); never invented
    document_date -> meeting_date (the day the meeting took place)
    creation_date -> transcribed_at | first_seen (when Brubru produced the row)

Per Victor's directive (1 June 2026): body_txt and body_html are ALWAYS
populated whenever the source has content — on both the list and the detail
endpoint. Because each transcript is heavy (20k-23k words / 40-140 KB), the
list default `limit` is small (10) and capped at 50; partners page through.
"""

from __future__ import annotations

import html as _html
from datetime import date, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.committee_meeting_transcript import (
    CommitteeMeetingTranscript,
    TranscriptStatusEnum,
)
from models.user import User

from ._body import body_threshold_param
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

router = APIRouter(prefix="/committee-transcripts", tags=["v1-committee-transcripts"])


def _committee_streaming_url(code: Optional[str]) -> Optional[str]:
    """Generic-but-real committee webstreaming page (last-resort public_url)."""
    if not code:
        return None
    return f"https://multimedia.europarl.europa.eu/en/webstreaming?committee={code.upper()}"


def _public_url(row: CommitteeMeetingTranscript) -> Optional[str]:
    """Citizen URL fallback chain — never synthesised beyond the real EP
    multimedia page for the committee."""
    return row.multimedia_url or row.video_url or _committee_streaming_url(row.committee_code)


def _enum_value(v: Any) -> Optional[str]:
    if v is None:
        return None
    return getattr(v, "value", None) or str(v)


def _compose_transcript_html(segments: Any, fallback_text: Optional[str]) -> Optional[str]:
    """Build body_html from the real transcript_segments JSON.

    Each segment is {start, end, text, speaker_label}. We emit one <p> per
    segment, prefixing the speaker label in <strong> when present. This is a
    faithful structuring of the SAME text we already hold — nothing invented.

    Falls back to wrapping the raw transcript_text in paragraphs (split on
    blank lines) when segments are absent. Returns None when there is no body.
    """
    parts: list[str] = []
    if isinstance(segments, list) and segments:
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            speaker = (seg.get("speaker_label") or seg.get("speaker") or "").strip()
            if speaker:
                parts.append(f"<p><strong>{_html.escape(speaker)}:</strong> {_html.escape(text)}</p>")
            else:
                parts.append(f"<p>{_html.escape(text)}</p>")
    if not parts and fallback_text and fallback_text.strip():
        for para in (p.strip() for p in fallback_text.split("\n\n")):
            if para:
                parts.append(f"<p>{_html.escape(para)}</p>")
    if not parts:
        return None
    return "<article>" + "".join(parts) + "</article>"


class CommitteeTranscriptOut(BaseModel):
    id: str
    committee_code: str
    title: str
    meeting_date: datetime
    event_id: Optional[str] = None
    multimedia_url: Optional[str] = None
    video_url: Optional[str] = None
    word_count: Optional[int] = None
    duration_seconds: Optional[int] = None
    speaker_count: Optional[int] = None
    language: Optional[str] = None
    status: Optional[str] = None
    agenda_items: list = Field(default_factory=list)
    related_procedure_refs: list = Field(default_factory=list)
    committee_minutes_id: Optional[str] = None
    transcription_model: Optional[str] = None
    has_body: bool = False

    # The 5 mandatory Brubru v1 datapoints (real data only).
    public_url: Optional[str] = Field(
        None,
        description="Citizen URL — EP Multimedia Centre page for the recording (multimedia_url -> video_url -> committee webstreaming page).",
    )
    body_txt: Optional[str] = Field(
        None,
        description="Verbatim Whisper transcript of the meeting. Null on the list endpoint unless include_body=true; always present on the detail endpoint.",
    )
    body_html: Optional[str] = Field(
        None,
        description="HTML rendering composed from transcript_segments (one <p> per segment, speaker label when known). Same text as body_txt, structured. Null unless include_body=true / detail.",
    )
    document_date: Optional[date] = Field(
        None,
        description="The date the committee meeting took place (meeting_date, date-only).",
    )
    creation_date: Optional[datetime] = Field(
        None,
        description="When Brubru produced this transcript row (transcribed_at, falling back to first_seen).",
    )


def _row_to_item(row: CommitteeMeetingTranscript, *, threshold: int) -> CommitteeTranscriptOut:
    # body_txt + body_html are ALWAYS populated when the row has a transcript
    # (Victor's directive, 1 June 2026). body_html is composed from the real
    # transcript_segments — same text, structured — never invented.
    text = row.transcript_text or ""
    has_body = bool(text and len(text) >= threshold)
    body_txt = text or None
    body_html = _compose_transcript_html(row.transcript_segments, row.transcript_text) if text else None

    return CommitteeTranscriptOut(
        id=str(row.id),
        committee_code=row.committee_code,
        title=row.title,
        meeting_date=row.meeting_date,
        event_id=row.event_id,
        multimedia_url=row.multimedia_url,
        video_url=row.video_url,
        word_count=row.word_count,
        duration_seconds=row.duration_seconds,
        speaker_count=row.speaker_count,
        language=row.language,
        status=_enum_value(row.status),
        agenda_items=list(row.agenda_items or []),
        related_procedure_refs=list(row.related_procedure_refs or []),
        committee_minutes_id=str(row.committee_minutes_id) if row.committee_minutes_id else None,
        transcription_model=row.transcription_model,
        has_body=has_body,
        # 5 mandatory datapoints
        public_url=_public_url(row),
        body_txt=body_txt,
        body_html=body_html,
        document_date=row.meeting_date.date() if hasattr(row.meeting_date, "date") else row.meeting_date,
        creation_date=row.transcribed_at or row.first_seen,
    )


@router.get(
    "",
    response_model=PaginatedResponse[CommitteeTranscriptOut],
    summary="EP committee meeting transcripts — full AI transcript of committee webstreams",
    description="""**What it does**
Returns AI-generated transcripts of European Parliament committee (and subcommittee) meetings, produced from the EP Multimedia Centre webstream recordings. Each row carries the committee, meeting date, title, word count, duration, mapped agenda items, the procedure references discussed, and a link to the official recording. This is the textual companion to `/api/v1/webstreams` (which gives the stream URL + transcript status); this endpoint gives the transcript content itself.

**When to use it**
To read what was actually said in a committee debate — search a committee's deliberations, pull every meeting that discussed a given procedure, or feed a verbatim debate record into your own analysis. For the official summary record instead, use `/api/v1/committees/{code}/minutes`.

**Input**
- `committee` — EP committee/subcommittee code (e.g. `LIBE`, `ENVI`, `DROI`).
- `procedure_reference` — return only meetings that discussed this procedure (e.g. `2024/0079(COD)`); matches the transcript's mapped `related_procedure_refs`.
- `q` — substring search across the meeting title and the transcript text.
- `has_transcript` — `true` (default) returns only meetings with a completed transcript; set `false` to also see scheduled/pending/failed rows.
- `status` — filter on processing status (`completed`, `pending`, `transcribing`, `failed`).
- `published_from` / `published_to` (aliased `date_from` / `date_to`) — `meeting_date` range.
- `updated_from` — rows updated at/after this timestamp (incremental sync).
- `body_threshold` — minimum transcript length (chars) for `has_body=true`. Default 500.
- `limit` (default 10, max 50 — bodies are always returned and each is large), `page` (1-indexed).

**Try it**
```
GET /api/v1/committee-transcripts?committee=LIBE
GET /api/v1/committee-transcripts?procedure_reference=2024/0079(COD)
GET /api/v1/committee-transcripts?committee=ENVI&limit=3
```

**You get back**
A `PaginatedResponse[CommitteeTranscriptOut]`. Each row carries `committee_code`, `title`, `meeting_date`, `word_count`, `duration_seconds`, `speaker_count`, `agenda_items[]`, `related_procedure_refs[]`, plus the 5 envelope datapoints: `public_url` (the recording page), `body_txt` + `body_html` (the full transcript — always populated when a transcript exists), `document_date` (the meeting date), and `creation_date` (when Brubru transcribed it).

**Data freshness**
Transcribed from EP Multimedia Centre recordings via OpenAI Whisper (`backend/scripts/transcribe_pending_committees.py`). New committee recordings appear on the Multimedia Centre within hours of a meeting; transcription runs as a batch job after the recording is published.""",
)
async def list_committee_transcripts(
    request: Request,
    committee: Optional[str] = Query(None, description="EP committee/subcommittee code (e.g. LIBE)."),
    procedure_reference: Optional[str] = Query(None, description="Return only meetings that discussed this procedure ref."),
    q: Optional[str] = Query(None, description="Substring search on title + transcript text."),
    has_transcript: bool = Query(True, description="True (default) = only meetings with a completed transcript."),
    status: Optional[str] = Query(None, description="completed | pending | transcribing | failed"),
    published_from: Optional[date] = Query(None, alias="date_from"),
    published_to: Optional[date] = Query(None, alias="date_to"),
    updated_from: Optional[datetime] = Query(None),
    body_threshold: int = Depends(body_threshold_param),
    limit: int = Query(10, ge=1, le=50, description="Items per page (default 10, max 50 — full body is always returned, each transcript is large)."),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CommitteeTranscriptOut]:
    T = CommitteeMeetingTranscript
    base = db.query(T)

    if committee:
        base = base.filter(func.upper(T.committee_code) == committee.upper())
    if procedure_reference:
        base = base.filter(T.related_procedure_refs.contains([procedure_reference]))
    if status:
        # Native enum stores the member NAME ("COMPLETED"). Map the input to a
        # member by name; an unknown value yields no rows rather than guessing.
        try:
            status_member = TranscriptStatusEnum[status.upper()]
            base = base.filter(T.status == status_member)
        except KeyError:
            base = base.filter(T.id.is_(None))
    if has_transcript:
        base = base.filter(T.transcript_text.isnot(None), func.length(T.transcript_text) > 0)
    if q:
        like = f"%{q}%"
        base = base.filter(or_(T.title.ilike(like), T.transcript_text.ilike(like)))
    if published_from:
        base = base.filter(T.meeting_date >= published_from)
    if published_to:
        base = base.filter(T.meeting_date <= datetime.combine(published_to, datetime.max.time()))
    if updated_from:
        base = base.filter(T.last_updated >= updated_from)

    total = base.count()
    rows = base.order_by(T.meeting_date.desc()).offset((page - 1) * limit).limit(limit).all()

    data = [_row_to_item(row, threshold=body_threshold) for row in rows]
    return build_envelope(
        data,
        total=total,
        page=page,
        limit=limit,
        published_from=published_from,
        published_to=published_to,
        updated_from=updated_from,
        coverage_complete=True,
        op_core_title="EP committee meeting transcripts",
        op_core_type="EP committee transcript",
        op_core_identifier=str(request.url),
        op_core_referenced_by=[
            "/api/v1/webstreams",
            "/api/v1/committees/{code}/minutes",
        ],
    )


@router.get(
    "/{transcript_id}",
    response_model=CommitteeTranscriptOut,
    summary="One committee meeting transcript by id — full transcript text + HTML",
    description="""**What it does**
Fetches a single committee meeting transcript by its Brubru-internal UUID, always with the full body: `body_txt` (the verbatim Whisper transcript) and `body_html` (the same text structured one paragraph per segment, with speaker labels when known).

**When to use it**
After locating a meeting via the list endpoint, use this to pull the complete transcript for display or downstream processing.

**Input**
- `transcript_id` (path) — the Brubru-internal UUID from the list endpoint's `id`.

**Try it**
```
GET /api/v1/committee-transcripts/{transcript_id}
```

**You get back**
A single `CommitteeTranscriptOut` (same shape as the list endpoint's `data[i]`), always with `body_txt` + `body_html` populated when a transcript exists, or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Transcribed from EP Multimedia Centre recordings via OpenAI Whisper. Re-transcription updates `creation_date` (transcribed_at).""",
)
async def get_committee_transcript_detail(
    transcript_id: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CommitteeTranscriptOut:
    row = db.query(CommitteeMeetingTranscript).filter(CommitteeMeetingTranscript.id == transcript_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"reason_code": "not_found", "message": f"No committee transcript with id {transcript_id}"})
    return _row_to_item(row, threshold=body_threshold)
