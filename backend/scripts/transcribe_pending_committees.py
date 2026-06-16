"""
Batch transcription of PENDING committee_meeting_transcripts rows that have a video_url.

Usage:
    # Transcribe most-recent meeting for each priority committee (dry-run to see what's queued)
    python3.12 -m scripts.transcribe_pending_committees --dry-run

    # Transcribe 1 meeting per priority committee (most recent first)
    python3.12 -m scripts.transcribe_pending_committees --limit-per-committee 1

    # Transcribe all ENVI and SANT meetings
    python3.12 -m scripts.transcribe_pending_committees --committee ENVI --committee SANT

    # Transcribe everything (150 meetings — ~$65, ~12 hrs)
    python3.12 -m scripts.transcribe_pending_committees --all

    # Pin to Voxtral (Mistral open-source ASR) — default
    python3.12 -m scripts.transcribe_pending_committees --engine voxtral --limit-per-committee 1

Engine priority: Voxtral (Mistral voxtral-mini-2507, MISTRAL_API_KEY) -> Whisper-1 (OPENAI_API_KEY).
Both are open-source models; Voxtral is primary.
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from dotenv import load_dotenv
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from core.database import SessionLocal
from models.committee_meeting_transcript import (
    CommitteeMeetingTranscript,
    TranscriptStatusEnum,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Pharma-first priority, then Brubru-broad
PRIORITY_COMMITTEES = [
    "SANT", "ENVI", "IMCO", "ITRE", "JURI", "EMPL",
    "LIBE", "AFET", "AGRI", "INTA", "BUDG", "AFCO",
    "ECON", "DROI", "TRAN", "REGI", "FEMM", "PETI",
    "CULT", "CONT", "DEVE", "SEDE", "HOUS", "FISC",
]


def _reset_stuck(session, hours: int = 2) -> int:
    """Self-heal: reset rows stuck in TRANSCRIBING longer than `hours` back to
    PENDING (a deploy or crash killed the worker mid-run). Idempotent."""
    from sqlalchemy import text as _t
    n = session.execute(_t(
        "UPDATE committee_meeting_transcripts SET status='PENDING' "
        "WHERE status='TRANSCRIBING' "
        "AND COALESCE(last_updated, first_seen, meeting_date) < NOW() - (:h || ' hours')::interval"
    ), {"h": hours}).rowcount
    session.commit()
    if n:
        logger.info("[reset] %d stuck TRANSCRIBING row(s) reset to PENDING", n)
    return n or 0


def _priority_committees(session) -> list:
    """Committees users actually care about, highest priority first:
    (1) committees on files users actively track, then
    (2) committees mapped from all users' Policy Interests.
    Falls back to the static PRIORITY_COMMITTEES tail."""
    from sqlalchemy import text as _t
    from services.tracking.pi_committee_crosswalk import committees_for_interests
    ordered: list = []
    seen: set = set()

    def _add(code):
        c = (code or "").upper().strip()
        if c and c not in seen:
            seen.add(c); ordered.append(c)

    # (1) committees on actively-tracked carriages (strongest signal)
    try:
        rows = session.execute(_t(
            "SELECT DISTINCT unnest(lc.committees) AS c "
            "FROM legislative_carriages lc "
            "JOIN user_carriage_tracks uct ON uct.carriage_id = lc.id "
            "WHERE uct.archived_at IS NULL AND lc.committees IS NOT NULL"
        )).fetchall()
        for r in rows:
            _add(r[0])
    except Exception as e:
        logger.warning("[priority] tracked-committee lookup failed: %s", e)

    # (2) committees mapped from every user's Policy Interests.
    # users.policy_interests is a JSON-array string in a text column, so parse it
    # in Python rather than unnesting in SQL.
    try:
        import json as _json
        interests: set = set()
        for (raw,) in session.execute(_t(
            "SELECT policy_interests FROM users WHERE policy_interests IS NOT NULL"
        )).fetchall():
            try:
                vals = _json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(vals, list):
                    interests.update(str(v) for v in vals if v)
            except Exception:
                continue
        for code in committees_for_interests(interests):
            _add(code)
    except Exception as e:
        logger.warning("[priority] PI-committee lookup failed: %s", e)

    # (3) static fallback tail
    for c in PRIORITY_COMMITTEES:
        _add(c)
    return ordered


def _fetch_pending(session, committees=None, limit_per_committee=None):
    """Return PENDING rows with video_url, ordered newest-first per committee."""
    from sqlalchemy import not_, or_
    base = (
        session.query(CommitteeMeetingTranscript)
        .filter(
            CommitteeMeetingTranscript.status == TranscriptStatusEnum.PENDING,
            CommitteeMeetingTranscript.video_url.isnot(None),
            not_(or_(
                CommitteeMeetingTranscript.event_id.ilike('%seed%'),
                CommitteeMeetingTranscript.event_id.ilike('%test%'),
            )),
        )
        .order_by(
            CommitteeMeetingTranscript.committee_code,
            CommitteeMeetingTranscript.meeting_date.desc(),
        )
    )

    if committees:
        codes_upper = [c.upper() for c in committees]
        from sqlalchemy import or_
        base = base.filter(
            or_(*[
                CommitteeMeetingTranscript.committee_code.ilike(f"%{c}%")
                for c in codes_upper
            ])
        )

    rows = base.all()

    # Tracked/PI-first ordering: rank by the user-priority committee list, then
    # newest meeting first. Unranked committees sort after ranked ones.
    priority = _priority_committees(session)
    rank = {c: i for i, c in enumerate(priority)}
    rows.sort(key=lambda r: (
        rank.get((r.committee_code or "")[:4].upper(), len(rank) + 1),
        rank.get((r.committee_code or "").upper(), len(rank) + 1),
        -(r.meeting_date.timestamp() if r.meeting_date else 0),
    ))

    if limit_per_committee:
        seen: dict = {}
        filtered = []
        for row in rows:
            # Use primary code (first 4 chars) for grouping joint committees
            key = row.committee_code[:4]
            count = seen.get(key, 0)
            if count < limit_per_committee:
                filtered.append(row)
                seen[key] = count + 1
        return filtered

    return rows


async def transcribe_batch(
    committees=None,
    limit_per_committee=None,
    engine=None,
    language="en",
    dry_run=False,
    max_total=None,
    reset_stuck=False,
):
    from services.committee_transcription_service import get_committee_transcription_service

    session = SessionLocal()
    try:
        if reset_stuck:
            _reset_stuck(session)
        rows = _fetch_pending(session, committees=committees, limit_per_committee=limit_per_committee)
        if max_total:
            rows = rows[:max_total]
        if not rows:
            logger.info("[batch] No PENDING rows with video_url found for the given filters.")
            return

        logger.info("[batch] %d meetings queued for transcription", len(rows))
        for row in rows:
            logger.info(
                "[batch]   %s | %s | %s",
                row.committee_code,
                row.meeting_date.strftime("%Y-%m-%d"),
                (row.title or "")[:80],
            )

        if dry_run:
            logger.info("[batch] --dry-run: no transcriptions started.")
            return

        svc = get_committee_transcription_service()
        total_cost = 0.0
        completed = 0
        failed = 0

        for i, row in enumerate(rows, 1):
            # Re-read status — a concurrent batch may have already processed this row.
            session.refresh(row)
            if row.status != TranscriptStatusEnum.PENDING:
                logger.info(
                    "[batch] [%d/%d] SKIP %s %s (status=%s — already handled)",
                    i, len(rows), row.committee_code,
                    row.meeting_date.strftime("%Y-%m-%d"), row.status,
                )
                continue

            logger.info(
                "[batch] [%d/%d] Transcribing %s %s ...",
                i, len(rows), row.committee_code, row.meeting_date.strftime("%Y-%m-%d"),
            )
            row.status = TranscriptStatusEnum.TRANSCRIBING
            session.commit()

            try:
                result = await svc.transcribe_meeting(
                    video_url=row.video_url,
                    committee_code=row.committee_code,
                    meeting_date=row.meeting_date.date(),
                    title=row.title or "",
                    agenda_items=row.agenda_items or [],
                    language=language,
                    engine=engine,
                )
                for k, v in result.items():
                    if hasattr(row, k):
                        setattr(row, k, v)
                if result.get("status") == "completed":
                    row.status = TranscriptStatusEnum.COMPLETED
                    row.transcribed_at = datetime.utcnow()
                    cost = result.get("transcription_cost") or 0.0
                    total_cost += cost
                    completed += 1
                    logger.info(
                        "[batch] [%d/%d] DONE: %s words, %d sec, $%.4f (running total $%.4f)",
                        i, len(rows),
                        result.get("word_count", 0),
                        result.get("duration_seconds", 0),
                        cost, total_cost,
                    )
                else:
                    row.status = TranscriptStatusEnum.FAILED
                    failed += 1
                    logger.warning(
                        "[batch] [%d/%d] FAILED: %s", i, len(rows), result.get("error_message", "?")
                    )
                session.commit()

            except Exception as exc:
                session.rollback()
                row.status = TranscriptStatusEnum.FAILED
                row.error_message = str(exc)[:500]
                session.commit()
                failed += 1
                logger.error("[batch] [%d/%d] Exception: %s", i, len(rows), exc)

        logger.info(
            "[batch] FINISHED: %d completed, %d failed, total cost $%.4f",
            completed, failed, total_cost,
        )

    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Batch transcribe PENDING EP committee meetings")
    parser.add_argument(
        "--committee", action="append", default=None,
        help="Committee code(s) to transcribe (repeatable). Default: all priority committees.",
    )
    parser.add_argument(
        "--limit-per-committee", type=int, default=None,
        help="Max meetings per committee code. Picks newest first.",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Transcribe all PENDING rows (ignores --committee filter).",
    )
    parser.add_argument(
        "--engine", type=str, default=None, choices=("faster-whisper", "voxtral", "whisper", "groq"),
        help="Pin ASR engine. groq = whisper-large-v3 on Groq free tier (cron default); "
             "faster-whisper = local/free but slow; voxtral/whisper = paid API.",
    )
    parser.add_argument(
        "--max", type=int, default=None, dest="max_total",
        help="Hard cap on total meetings transcribed this run (across all committees). "
             "Use for the proactive cron so each run is bounded.",
    )
    parser.add_argument(
        "--reset-stuck", action="store_true",
        help="Reset rows stuck in TRANSCRIBING > 2h back to PENDING before running "
             "(self-heal from a deploy-killed or crashed run).",
    )
    parser.add_argument(
        "--language", type=str, default="en",
        help="Interpretation booth language (en/fr/es/it/nl/floor). Default 'en'.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be transcribed without actually running.",
    )
    args = parser.parse_args()

    committees = None if args.all else (args.committee or PRIORITY_COMMITTEES)

    asyncio.run(transcribe_batch(
        committees=committees,
        limit_per_committee=args.limit_per_committee,
        engine=args.engine,
        language=args.language,
        dry_run=args.dry_run,
        max_total=args.max_total,
        reset_stuck=args.reset_stuck,
    ))


if __name__ == "__main__":
    main()
