"""
Seed a REAL EP committee meeting transcript into the EFPIA demo account's MEUB
Documents. Reads from committee_meeting_transcripts (status=COMPLETED), formats
as Markdown, stores as a user_document (document_type='note',
doc_metadata.original_document_type='transcript').

Default target meeting: SANT 23 April 2026 0900 (Committee on Public Health
Ordinary meeting). Override with --event-id.

Usage:
    cd backend && python3.12 scripts/seed_efpia_committee_transcript.py            # dry-run
    cd backend && python3.12 scripts/seed_efpia_committee_transcript.py --apply
    cd backend && python3.12 scripts/seed_efpia_committee_transcript.py --apply --event-id sant-committee-meeting_20260423-0900-COMMITTEE-SANT_vd
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(_BACKEND_DIR), ".env"))

from sqlalchemy import text
from core.database import SessionLocal, engine

engine.echo = False
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
for n in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    logging.getLogger(n).setLevel(logging.WARNING)

DEMO_EMAIL = "public-affairs@efpia.eu"
DEFAULT_EVENT_ID = "sant-committee-meeting_20260423-0900-COMMITTEE-SANT_vd"
MAX_CHARS = 45000


def build_markdown(row) -> str:
    meeting_date = row.meeting_date
    title = row.title or f"{row.committee_code} committee meeting"
    multimedia_url = row.multimedia_url or ""
    duration_min = int((row.duration_seconds or 0) / 60)
    cost = row.transcription_cost or 0.0
    model = row.transcription_model or "whisper-1"
    agenda = []
    if row.agenda_items:
        try:
            agenda = row.agenda_items if isinstance(row.agenda_items, list) else json.loads(row.agenda_items)
        except Exception:
            agenda = []

    lines = [
        f"# {row.committee_code} committee meeting -- {meeting_date.strftime('%d %B %Y')}",
        f"## {title}",
        "",
        f"_AI-generated transcript of the European Parliament {row.committee_code} committee meeting "
        f"of {meeting_date.strftime('%A, %d %B %Y')}. Source: EP Multimedia Centre recording "
        f"(English interpretation booth). Engine: {model}. Duration: {duration_min} minutes "
        f"({row.word_count or 0:,} words). Cost: USD {cost:.2f}._",
        "",
        f"Source page: {multimedia_url}",
        "",
    ]

    if agenda:
        lines.append("### Agenda")
        for item in agenda:
            num = item.get("number", "-")
            t = item.get("title", "")
            refs = ", ".join(item.get("procedure_refs") or [])
            ref_part = f" [{refs}]" if refs else ""
            ts = ""
            if item.get("start_time") is not None:
                mins = int(float(item["start_time"]) / 60)
                ts = f" (at {mins} min)"
            lines.append(f"- {num}. {t}{ref_part}{ts}")
        lines.append("")

    refs = row.related_procedure_refs or []
    if refs:
        lines.append("### Procedure references discussed")
        for r in refs:
            lines.append(f"- {r}")
        lines.append("")

    lines.append("### Transcript")
    lines.append("")
    transcript = (row.transcript_text or "").strip()
    body = "\n".join(lines) + transcript
    if len(body) > MAX_CHARS:
        body = body[:MAX_CHARS] + "\n\n[Transcript truncated for length]"
    return body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Persist changes (default dry-run).")
    ap.add_argument("--event-id", type=str, default=DEFAULT_EVENT_ID,
                    help=f"committee_meeting_transcripts.event_id to seed (default: {DEFAULT_EVENT_ID}).")
    ap.add_argument("--email", type=str, default=DEMO_EMAIL,
                    help=f"Destination user email (default: {DEMO_EMAIL}).")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        row = db.execute(text("""
            SELECT id, committee_code, meeting_date, title, multimedia_url, video_url,
                   transcript_text, word_count, duration_seconds, status, transcription_cost,
                   transcription_model, agenda_items, related_procedure_refs, language
            FROM committee_meeting_transcripts
            WHERE event_id = :eid
        """), {"eid": args.event_id}).first()
        if not row:
            logger.error(f"event_id={args.event_id} not in committee_meeting_transcripts")
            return 1

        status = str(getattr(row, "status", "")).lower()
        if "completed" not in status:
            logger.error(f"Transcript status is {status!r} (need 'completed'). Run the transcription first.")
            return 1
        if not (row.transcript_text and len(row.transcript_text) > 200):
            logger.error("Transcript text empty or too short. Aborting.")
            return 1

        content = build_markdown(row)
        title = (
            f"{row.committee_code} committee meeting transcript -- "
            f"{row.meeting_date.strftime('%d %B %Y')} -- {row.title[:60]}"
        )
        logger.info(f"Source: {row.committee_code} on {row.meeting_date.date()} ({row.word_count or 0:,} words, "
                    f"USD {row.transcription_cost or 0:.2f} via {row.transcription_model or 'whisper-1'})")
        logger.info(f"Doc title : {title}")
        logger.info(f"Doc length: {len(content):,} chars")

        uid = db.execute(text("SELECT id::text FROM users WHERE email = :e"), {"e": args.email}).scalar()
        if not uid:
            logger.error(f"User {args.email} not found")
            return 1

        exists = db.execute(text(
            "SELECT id FROM user_documents WHERE user_id = :u AND title = :t"
        ), {"u": uid, "t": title}).first()
        if exists:
            logger.info("[doc] SKIP -- already present.")
            return 0

        if not args.apply:
            logger.info("[doc] dry-run (use --apply to write)")
            return 0

        meta = {
            "original_document_type": "transcript",
            "source": "ep_committee_whisper" if "whisper" in (row.transcription_model or "") else "ep_committee_voxtral",
            "event_id": args.event_id,
            "meeting_date": row.meeting_date.date().isoformat(),
            "committee_code": row.committee_code,
            "multimedia_url": row.multimedia_url,
            "engine": row.transcription_model,
            "booth_language": (row.language or "en").lower(),
            "duration_seconds": row.duration_seconds,
            "word_count": row.word_count,
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
            "id": str(uuid.uuid4()),
            "u": uid,
            "title": title,
            "content": content,
            "areas": ["Public Health", "Pharmaceutical Legislation"],
            "tags": ["ep-committee", "transcript", row.committee_code.lower()],
            "exec": (f"AI transcript of the European Parliament {row.committee_code} committee meeting on "
                     f"{row.meeting_date.strftime('%d %B %Y')} ({(row.word_count or 0):,} words, "
                     f"{(row.duration_seconds or 0) // 60} minutes). English interpretation booth, "
                     f"engine {row.transcription_model}."),
            "meta": json.dumps(meta),
        })
        db.commit()
        logger.info("[doc] CREATE committed.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
