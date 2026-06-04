"""
Transcripts API (MEUB Section 3) - surfaces the EP transcription pipeline to users.

Phase 1 (1 Jun 2026): catalog of COMPLETED committee transcripts + PI-suggested
recordings available to transcribe + ON-DEMAND transcription (Blue tier only) +
save-to-My-Files. Wraps the existing committee_transcription_service / Whisper-
Voxtral pipeline and the committee_meeting_transcripts table - no new ASR code.

Read access: Yellow+ (same as the rest of MEUB). Triggering a transcription:
Blue only (cost ~USD 0.40-0.70/meeting; once produced, the COMPLETED row is shared
with everyone). NO Anthropic (transcription is non-chat; Voxtral/Whisper only).
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

from core.database import get_db, SessionLocal
from models.user import User
from models.committee_meeting_transcript import (
    CommitteeMeetingTranscript as CMT,
    TranscriptStatusEnum,
)
from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.pi_committee_crosswalk import (
    committees_for_interests, dgs_for_interests, council_configs_for_interests, keywords_for_interests,
)
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/transcripts", tags=["Transcripts"])

_MAX_DOC_CHARS = 90_000

# In-process progress for running jobs (single-process dev/prod). {id: {stage, pct}}.
# Background task updates it; /status reads it. Cleared when the job settles.
_PROGRESS: dict = {}


# ---------------------------------------------------------------------------
# Guards + helpers
# ---------------------------------------------------------------------------

def _require_yellow(user: User):
    if not user or user.subscription_tier == "white":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Transcripts require Yellow or Blue tier.")


def _is_blue_or_admin(user: User) -> bool:
    return bool(user and (user.subscription_tier == "blue" or getattr(user, "is_admin", False)))


def _pi_committees(user: User) -> set:
    return committees_for_interests(_interest_list(user)) or set()


def _apply_pi(q, user: User):
    """PI filter across institutions. Matches the body code against the user's
    EP committees / EC DGs / Council configurations (works whenever a row is
    body-coded), plus a title-keyword fallback for body-less AV (press statements,
    briefings). No interests -> unchanged."""
    interests = _interest_list(user)
    if not interests:
        return q
    codes = (committees_for_interests(interests) or set()) \
        | (dgs_for_interests(interests) or set()) \
        | (council_configs_for_interests(interests) or set())
    kws = keywords_for_interests(interests) or set()
    clauses = []
    if codes:
        clauses.append(CMT.committee_code.in_(list(codes)))
    for kw in kws:
        clauses.append(and_(CMT.institution != "EP", CMT.title.ilike(f"%{kw}%")))
    return q.filter(or_(*clauses)) if clauses else q


def _not_seed(q):
    """Exclude synthetic/seed fixtures (libe-seed contamination guard)."""
    return q.filter(
        ~CMT.event_id.ilike("%seed%"),
        ~CMT.event_id.ilike("%test%"),
        ~CMT.title.ilike("%synthetic%"),
    )


def _summary(r: CMT) -> dict:
    return {
        "id": str(r.id),
        "institution": getattr(r, "institution", "EP") or "EP",
        "committee_code": r.committee_code,
        "meeting_date": r.meeting_date.date().isoformat() if r.meeting_date else None,
        "title": r.title,
        "language": (r.language or "EN"),
        "word_count": r.word_count or 0,
        "duration_minutes": int((r.duration_seconds or 0) / 60),
        "procedure_refs": r.related_procedure_refs or [],
        "status": str(r.status.value if hasattr(r.status, "value") else r.status).lower(),
        "has_recording": bool(r.video_url),
        "has_agenda": bool(r.agenda_items),
    }


# ---------------------------------------------------------------------------
# Agenda linking (OJ -> items -> per-item timestamps)
# ---------------------------------------------------------------------------

def _session_start_from_url(video_url: Optional[str]) -> Optional[str]:
    """Recording start clock (HH:MM) from the dashed mediaKey in the HLS URL."""
    m = re.search(r"\d{8}-(\d{2})(\d{2})-", video_url or "")
    return f"{m.group(1)}:{m.group(2)}" if m else None


def _resolve_agenda(r: CMT) -> Optional[list]:
    """Discover the committee OJ for this recording, keep the items for its
    session, and align them to the stored transcript segments. EP committees
    only (PLENARY uses official CRE text; EC/Council have no committee OJ).
    Returns the aligned agenda items, or None. Best-effort, never raises."""
    inst = getattr(r, "institution", "EP") or "EP"
    if inst != "EP" or (r.committee_code or "").upper() == "PLENARY":
        return None
    try:
        from services.scrapers.committee_agenda_pdf import discover_agenda, items_for_session
        disc = discover_agenda(r.committee_code, r.meeting_date.date())
        if not disc:
            return None
        items = items_for_session(
            disc["parsed"], r.meeting_date.date(), _session_start_from_url(r.video_url))
        if not items:
            return None
        for it in items:
            it["agenda_source_url"] = disc["url"]
        segments = r.transcript_segments or []
        if segments:
            from services.committee_transcription_service import CommitteeTranscriptionService
            items = CommitteeTranscriptionService()._map_agenda_to_timestamps(items, segments)
        return items
    except Exception as e:
        logger.warning("[transcripts] agenda resolve failed for %s: %s", r.id, e)
        return None


# ---------------------------------------------------------------------------
# Catalog + detail
# ---------------------------------------------------------------------------

@router.get("/facets")
def facets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Institutions + their bodies present in the library, for the cascade filter."""
    _require_yellow(user)
    rows = _not_seed(
        db.query(CMT.institution, CMT.committee_code).distinct()
    ).all()
    bodies: dict = {}
    for inst, body in rows:
        bodies.setdefault(inst or "EP", set()).add(body)
    order = ["EP", "EC", "COUNCIL"]
    insts = sorted(bodies.keys(), key=lambda i: order.index(i) if i in order else 99)
    return {"institutions": insts,
            "bodies": {i: sorted(b for b in bodies[i] if b) for i in insts}}


@router.get("")
def list_transcripts(
    my_interests: bool = Query(False, description="Restrict to the user's Policy Interests"),
    institution: Optional[str] = Query(None),
    body: Optional[str] = Query(None, description="Body code (EP committee / EC DG / Council config)"),
    search: Optional[str] = Query(None),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Catalog of COMPLETED transcripts (the shared library)."""
    _require_yellow(user)
    q = _not_seed(
        db.query(CMT).filter(
            CMT.status == TranscriptStatusEnum.COMPLETED,
            CMT.transcript_text.isnot(None),
        )
    )
    if my_interests:
        q = _apply_pi(q, user)
    if institution:
        q = q.filter(CMT.institution == institution)
    if body:
        q = q.filter(CMT.committee_code == body)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(CMT.title.ilike(like), CMT.transcript_text.ilike(like)))
    total = q.count()
    rows = q.order_by(CMT.meeting_date.desc()).offset(offset).limit(limit).all()
    return {"total": total, "items": [_summary(r) for r in rows]}


@router.get("/suggestions")
def suggestions(
    my_interests: bool = Query(True, description="PI-filter the suggestions (Brubru proposes relevant). False = all."),
    institution: Optional[str] = Query(None),
    body: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Recordings available to transcribe (PENDING + recording URL). With
    my_interests, PI-matched (EP committee / EC-Council title keyword); else all."""
    _require_yellow(user)
    q = _not_seed(
        db.query(CMT).filter(
            CMT.status == TranscriptStatusEnum.PENDING,
            CMT.video_url.isnot(None),
        )
    )
    if my_interests:
        q = _apply_pi(q, user)
    if institution:
        q = q.filter(CMT.institution == institution)
    if body:
        q = q.filter(CMT.committee_code == body)
    rows = q.order_by(CMT.meeting_date.desc()).limit(60).all()
    # Hide recordings whose committee + day is ALREADY completed (possibly under
    # another event_id) so we never suggest re-transcribing a done meeting.
    done = {
        (c, d.date()) for (c, d) in db.query(CMT.committee_code, CMT.meeting_date)
        .filter(CMT.status == TranscriptStatusEnum.COMPLETED).all()
    }
    rows = [r for r in rows if (r.committee_code, r.meeting_date.date()) not in done][:40]
    return {"items": [_summary(r) for r in rows], "can_transcribe": _is_blue_or_admin(user)}


@router.get("/{tid}")
def get_transcript(
    tid: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_yellow(user)
    r = db.query(CMT).filter(CMT.id == tid).first()
    if not r:
        raise HTTPException(status_code=404, detail="Transcript not found.")
    out = _summary(r)
    # Compact segments {s: start_sec, t: text} power the synchronised transcript
    # (click a line -> seek the video; auto-highlight the active line). Capped to
    # keep the payload lean; very long debates fall back to paragraph text.
    segs = r.transcript_segments or []
    compact = None
    if 0 < len(segs) <= 4000:
        compact = [{"s": round(float(x.get("start") or 0), 1), "t": x.get("text") or ""}
                   for x in segs if (x.get("text") or "").strip()]
    out.update({
        "transcript_text": r.transcript_text,
        "agenda_items": r.agenda_items or [],
        "segments": compact,
        "video_url": r.video_url,
        "speakers": r.speakers or [],
        "multimedia_url": r.multimedia_url,
        "engine": r.transcription_model,
        "error_message": r.error_message,
        "summary_langs": sorted((r.summaries or {}).keys()),
    })
    return out


# ---------------------------------------------------------------------------
# Multilingual institutional summaries (Qwen3-30B + Qwen3-235B-Instruct)
# ---------------------------------------------------------------------------

def _summary_payload(r: CMT, lang: str, user: User) -> dict:
    sums = r.summaries or {}
    entry = sums.get(lang) or {}
    return {
        "id": str(r.id),
        "lang": lang,
        "available_langs": sorted(sums.keys()),
        "summary": entry.get("text"),
        "model": entry.get("model"),
        "generated_at": entry.get("generated_at"),
        "can_generate": _is_blue_or_admin(user),
    }


@router.get("/{tid}/summary")
def get_summary(
    tid: str,
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cached institutional summary in `lang` (en|es|fr|it|nl|ca), or null if not
    generated yet. Yellow+."""
    _require_yellow(user)
    r = db.query(CMT).filter(CMT.id == tid).first()
    if not r:
        raise HTTPException(status_code=404, detail="Transcript not found.")
    return _summary_payload(r, (lang or "en").lower(), user)


@router.post("/{tid}/summary")
async def generate_summary(
    tid: str,
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate the summary in `lang`. The canonical English summary is produced
    first (Qwen3-30B) if missing; non-English langs are translated on demand
    (Qwen3-235B-Instruct-2507). Cached + shared once made. Blue tier only."""
    if not _is_blue_or_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Generating summaries is a Professional (Blue) feature.")
    lang = (lang or "en").lower()
    from services.transcript_summary_service import (
        summarise_english, translate_summary, SUPPORTED_LANGS,
        SUMMARISER_MODEL, TRANSLATOR_MODEL,
    )
    if lang not in SUPPORTED_LANGS:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {lang}")
    r = db.query(CMT).filter(CMT.id == tid).first()
    if not r:
        raise HTTPException(status_code=404, detail="Transcript not found.")
    if not (r.transcript_text and len(r.transcript_text) > 400):
        raise HTTPException(status_code=400, detail="Transcript is not long enough to summarise.")

    sums = dict(r.summaries or {})
    now = datetime.utcnow().isoformat()
    date_str = r.meeting_date.strftime("%d %B %Y") if r.meeting_date else ""

    if "en" not in sums:
        en = await summarise_english(
            r.transcript_text, r.committee_code, date_str, r.title or "", r.agenda_items or None)
        if not en:
            raise HTTPException(status_code=502, detail="Summary generation failed.")
        sums["en"] = {"text": en, "model": SUMMARISER_MODEL, "generated_at": now}

    if lang != "en" and lang not in sums:
        tr = await translate_summary(sums["en"]["text"], lang)
        if not tr:
            raise HTTPException(status_code=502, detail="Translation failed.")
        sums[lang] = {"text": tr, "model": TRANSLATOR_MODEL, "generated_at": now}

    r.summaries = sums
    db.commit()
    return _summary_payload(r, lang, user)


@router.post("/{tid}/agenda")
def attach_agenda(
    tid: str,
    refresh: bool = Query(False, description="Re-fetch even if an agenda is already attached"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Link this recording to its committee agenda (OJ): discover the OJ PDF,
    parse its items, and align them to the transcript as clickable chapters.
    Cheap (no ASR, no LLM); the result is shared with everyone. Yellow+."""
    _require_yellow(user)
    r = db.query(CMT).filter(CMT.id == tid).first()
    if not r:
        raise HTTPException(status_code=404, detail="Transcript not found.")
    if r.agenda_items and not refresh:
        return {"id": str(r.id), "agenda_items": r.agenda_items, "cached": True}
    items = _resolve_agenda(r)
    if not items:
        raise HTTPException(status_code=404, detail="No matching committee agenda found for this recording.")
    r.agenda_items = items
    db.commit()
    return {"id": str(r.id), "agenda_items": items, "cached": False}


@router.get("/{tid}/status")
def transcript_status(
    tid: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Poll a transcription job (the row's status)."""
    _require_yellow(user)
    r = db.query(CMT).filter(CMT.id == tid).first()
    if not r:
        raise HTTPException(status_code=404, detail="Transcript not found.")
    prog = _PROGRESS.get(tid) or {}
    return {
        "id": str(r.id),
        "status": str(r.status.value if hasattr(r.status, "value") else r.status).lower(),
        "stage": prog.get("stage"),
        "progress": prog.get("pct"),
        "word_count": r.word_count or 0,
        "error_message": r.error_message,
    }


# ---------------------------------------------------------------------------
# On-demand transcription (Blue only)
# ---------------------------------------------------------------------------

@router.post("/{tid}/transcribe", status_code=202)
def transcribe(
    tid: str,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Trigger transcription of a discovered recording. Blue tier only."""
    if not _is_blue_or_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="On-demand transcription is a Professional (Blue) feature.")
    r = db.query(CMT).filter(CMT.id == tid).first()
    if not r:
        raise HTTPException(status_code=404, detail="Recording not found.")
    cur = str(r.status.value if hasattr(r.status, "value") else r.status).lower()
    if cur == "completed":
        return {"id": str(r.id), "status": "completed", "message": "Already transcribed."}
    if cur in ("transcribing", "downloading", "processing"):
        return {"id": str(r.id), "status": cur, "message": "Transcription already in progress."}
    if not r.video_url:
        raise HTTPException(status_code=400, detail="No recording available for this meeting.")
    r.status = TranscriptStatusEnum.TRANSCRIBING
    r.error_message = None
    db.commit()
    bg.add_task(_run_transcription, str(r.id))
    return {"id": str(r.id), "status": "transcribing", "message": "Transcription started."}


def _run_transcription(tid: str) -> None:
    """Background worker: ffmpeg + Voxtral/Whisper over the stored recording URL."""
    import asyncio
    db = SessionLocal()
    try:
        r = db.query(CMT).filter(CMT.id == tid).first()
        if not r or not r.video_url:
            return
        from services.committee_transcription_service import CommitteeTranscriptionService
        svc = CommitteeTranscriptionService()
        _PROGRESS[tid] = {"stage": "preparing", "pct": 0}

        def _cb(stage: str, pct: float):
            _PROGRESS[tid] = {"stage": stage, "pct": round(pct, 1)}

        result = asyncio.run(svc.transcribe_meeting(
            video_url=r.video_url,
            committee_code=r.committee_code,
            meeting_date=r.meeting_date.date(),
            title=r.title,
            agenda_items=r.agenda_items or None,
            language=(r.language or "en").lower(),
            engine="voxtral",  # on-demand: fast API (voxtral->whisper), never slow local CPU
            progress_cb=_cb,
        ))
        text_out = (result or {}).get("transcript_text")
        if text_out and len(text_out) > 200:
            r.transcript_text = text_out
            r.transcript_segments = result.get("transcript_segments") or []
            r.word_count = result.get("word_count")
            r.duration_seconds = result.get("duration_seconds")
            r.related_procedure_refs = result.get("related_procedure_refs") or []
            if result.get("agenda_items"):
                r.agenda_items = result["agenda_items"]
            r.transcription_cost = result.get("transcription_cost")
            r.transcription_model = result.get("transcription_model")
            r.language = (result.get("transcription_language") or r.language or "en").upper()
            r.status = TranscriptStatusEnum.COMPLETED
            r.transcribed_at = datetime.utcnow()
            # Best-effort: link the committee agenda (OJ) as clickable chapters.
            # Never let an agenda hiccup fail the transcription itself.
            try:
                if not r.agenda_items:
                    agenda = _resolve_agenda(r)
                    if agenda:
                        r.agenda_items = agenda
            except Exception as ae:
                logger.warning("[transcripts] post-transcription agenda link failed: %s", ae)
        else:
            r.status = TranscriptStatusEnum.FAILED
            r.error_message = (result or {}).get("error_message") or "Transcription produced no usable text."
        db.commit()
    except Exception as e:
        logger.exception("[transcripts] transcription failed for %s: %s", tid, e)
        try:
            db.rollback()
            r = db.query(CMT).filter(CMT.id == tid).first()
            if r:
                r.status = TranscriptStatusEnum.FAILED
                r.error_message = str(e)[:500]
                db.commit()
        except Exception:
            db.rollback()
    finally:
        _PROGRESS.pop(tid, None)
        db.close()


# ---------------------------------------------------------------------------
# Save to My Files
# ---------------------------------------------------------------------------

def _build_markdown(r: CMT) -> str:
    md = r.meeting_date
    duration_min = int((r.duration_seconds or 0) / 60)
    lines = [
        f"# {r.committee_code} committee meeting -- {md.strftime('%d %B %Y')}",
        f"## {r.title or ''}",
        "",
        (f"_AI-generated transcript of the European Parliament {r.committee_code} committee meeting "
         f"of {md.strftime('%A, %d %B %Y')}. Source: EP Multimedia Centre recording. "
         f"Engine: {r.transcription_model or 'whisper-1'}. Duration: {duration_min} minutes "
         f"({(r.word_count or 0):,} words)._"),
        "",
    ]
    if r.related_procedure_refs:
        lines.append("### Procedure references discussed")
        lines += [f"- {ref}" for ref in r.related_procedure_refs]
        lines.append("")
    lines += ["### Transcript", ""]
    body = "\n".join(lines) + (r.transcript_text or "").strip()
    if len(body) > _MAX_DOC_CHARS:
        body = body[:_MAX_DOC_CHARS] + "\n\n[Transcript truncated for length]"
    return body


@router.post("/{tid}/save-to-files")
def save_to_files(
    tid: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Write a COMPLETED transcript into the user's My Files. Blue tier only."""
    if not _is_blue_or_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Saving transcripts to My Files is a Professional (Blue) feature.")
    r = db.query(CMT).filter(CMT.id == tid).first()
    if not r:
        raise HTTPException(status_code=404, detail="Transcript not found.")
    if str(r.status.value if hasattr(r.status, "value") else r.status).lower() != "completed" \
            or not (r.transcript_text and len(r.transcript_text) > 200):
        raise HTTPException(status_code=400, detail="Transcript is not ready.")

    doc_id = str(uuid.uuid4())
    title = (f"{r.committee_code} committee meeting transcript -- "
             f"{r.meeting_date.strftime('%d %B %Y')} -- {(r.title or '')[:60]}")
    meta = {
        "original_document_type": "transcript",
        "source": "ep_committee_voxtral" if "voxtral" in (r.transcription_model or "") else "ep_committee_whisper",
        "event_id": r.event_id,
        "meeting_date": r.meeting_date.date().isoformat(),
        "committee_code": r.committee_code,
        "engine": r.transcription_model,
        "duration_seconds": r.duration_seconds,
        "word_count": r.word_count,
    }
    db.execute(text("""
        INSERT INTO user_documents (id, user_id, document_type, title, content,
            policy_areas, tags, executive_summary, doc_metadata,
            include_in_ai_context, is_private, version, view_count, is_featured,
            created_at, updated_at)
        VALUES (:id, :u, 'note', :title, :content,
                :areas, :tags, :exec, CAST(:meta AS jsonb),
                true, true, 1, 0, false, NOW(), NOW())
    """), {
        "id": doc_id,
        "u": str(user.id),
        "title": title,
        "content": _build_markdown(r),
        "areas": [],
        "tags": ["ep-committee", "transcript", (r.committee_code or "").lower()],
        "exec": (f"AI transcript of the European Parliament {r.committee_code} committee meeting on "
                 f"{r.meeting_date.strftime('%d %B %Y')} ({(r.word_count or 0):,} words, "
                 f"{(r.duration_seconds or 0) // 60} minutes)."),
        "meta": json.dumps(meta),
    })
    db.commit()
    return {"document_id": doc_id, "title": title}
