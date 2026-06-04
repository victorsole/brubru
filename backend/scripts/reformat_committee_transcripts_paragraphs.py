"""
Backfill: re-render `committee_meeting_transcripts.transcript_text` from
`transcript_segments` using the paragraph formatter so existing rows stop
showing up as a single wall of text. Also refresh any `user_documents`
rows whose `doc_metadata.original_document_type='transcript'` for matching
event_ids -- their `content` embeds the old un-paragraphed transcript.

Usage:
    cd backend && python3.12 scripts/reformat_committee_transcripts_paragraphs.py            # dry-run
    cd backend && python3.12 scripts/reformat_committee_transcripts_paragraphs.py --apply
    cd backend && python3.12 scripts/reformat_committee_transcripts_paragraphs.py --apply --event-id <id>
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Optional

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(_BACKEND_DIR), ".env"))

from sqlalchemy import text
from core.database import SessionLocal, engine
from services.committee_transcription_service import format_segments_as_paragraphs

engine.echo = False
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
for n in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    logging.getLogger(n).setLevel(logging.WARNING)


def _coerce_segments(raw) -> list:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return []


def _build_doc_markdown(row, transcript_text: str) -> str:
    """Mirror seed_efpia_committee_transcript.build_markdown so the doc
    refresh stays in lockstep with the seed script's format."""
    title = row["title"] or f"{row['committee_code']} committee meeting"
    duration_min = int((row["duration_seconds"] or 0) / 60)
    model = row["transcription_model"] or "whisper-1"
    cost = row["transcription_cost"] or 0.0
    md = row["meeting_date"]
    multimedia_url = row["multimedia_url"] or ""
    agenda = []
    if row["agenda_items"]:
        try:
            agenda = row["agenda_items"] if isinstance(row["agenda_items"], list) else json.loads(row["agenda_items"])
        except Exception:
            agenda = []

    lines = [
        f"# {row['committee_code']} committee meeting -- {md.strftime('%d %B %Y')}",
        f"## {title}",
        "",
        f"_AI-generated transcript of the European Parliament {row['committee_code']} committee meeting "
        f"of {md.strftime('%A, %d %B %Y')}. Source: EP Multimedia Centre recording "
        f"(English interpretation booth). Engine: {model}. Duration: {duration_min} minutes "
        f"({row['word_count'] or 0:,} words). Cost: USD {cost:.2f}._",
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

    refs = row["related_procedure_refs"] or []
    if refs:
        lines.append("### Procedure references discussed")
        for r in refs:
            lines.append(f"- {r}")
        lines.append("")

    lines.append("### Transcript")
    lines.append("")
    body = "\n".join(lines) + (transcript_text or "")
    if len(body) > 45000:
        body = body[:45000] + "\n\n[Transcript truncated for length]"
    return body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--event-id", type=str, default=None,
                    help="Restrict to a single event_id (default: all COMPLETED rows).")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        where = "WHERE status = 'COMPLETED'"
        params: dict = {}
        if args.event_id:
            where += " AND event_id = :eid"
            params["eid"] = args.event_id

        rows = db.execute(text(f"""
            SELECT id, event_id, committee_code, meeting_date, title,
                   transcript_text, transcript_segments,
                   multimedia_url, transcription_model, transcription_cost,
                   duration_seconds, word_count, agenda_items, related_procedure_refs
            FROM committee_meeting_transcripts
            {where}
            ORDER BY meeting_date DESC
        """), params).mappings().fetchall()

        if not rows:
            logger.info("No COMPLETED rows match. Nothing to do.")
            return 0

        transcript_updates = 0
        doc_updates = 0
        for r in rows:
            segs = _coerce_segments(r["transcript_segments"])
            if not segs:
                logger.info(f"[skip] {r['event_id']}: no segments")
                continue
            old_text = r["transcript_text"] or ""
            new_text = format_segments_as_paragraphs(segs)
            old_paras = old_text.count("\n\n") + 1 if old_text else 0
            new_paras = new_text.count("\n\n") + 1 if new_text else 0
            logger.info(
                f"[{r['committee_code']} {r['meeting_date'].date()}] "
                f"segments={len(segs)} old_paras={old_paras} new_paras={new_paras} "
                f"old_chars={len(old_text)} new_chars={len(new_text)}"
            )

            if args.apply and new_text and new_text != old_text:
                db.execute(text("""
                    UPDATE committee_meeting_transcripts
                    SET transcript_text = :t, last_updated = NOW()
                    WHERE id = :id
                """), {"t": new_text, "id": r["id"]})
                transcript_updates += 1

                # Refresh user_documents rows that embed this transcript
                doc_rows = db.execute(text("""
                    SELECT id FROM user_documents
                    WHERE doc_metadata @> jsonb_build_object(
                        'original_document_type', 'transcript',
                        'event_id', :eid
                    )
                """), {"eid": r["event_id"]}).fetchall()
                if doc_rows:
                    new_md = _build_doc_markdown(r, new_text)
                    for d in doc_rows:
                        db.execute(text("""
                            UPDATE user_documents
                            SET content = :c, updated_at = NOW()
                            WHERE id = :id
                        """), {"c": new_md, "id": d[0]})
                        doc_updates += 1

        if args.apply:
            db.commit()
            logger.info(f"\nUpdated {transcript_updates} transcripts and {doc_updates} user_documents rows.")
        else:
            logger.info("\n[dry-run] Re-run with --apply to persist.")
        return 0
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed: {exc!r}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
