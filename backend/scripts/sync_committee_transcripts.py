"""
EP Committee Meeting Transcripts -- sync CLI.

Discovery is the DEFAULT mode (safe to run from /news morning routine).
Transcription is opt-in via --transcribe (costs ~$0.006/min via Whisper).

Modes:

  1. `--seed-test-data`   -> insert one synthetic transcript row (no cost).
                              For wiring / chatbot tests.

  2. (default) `--discover [--committee LIBE] [--max 50] [--days 30]`
                          -> scrape the EP committees hub
                             (europarl.europa.eu/committees/en/meetings/webstreaming),
                             insert PENDING rows with video_url. Idempotent.

  3. `... --transcribe`   -> ALSO run Whisper on any newly-discovered rows.
                             Intended for scheduled batch, not /news.

Usage:
    python3.12 -m scripts.sync_committee_transcripts --seed-test-data
    python3.12 -m scripts.sync_committee_transcripts                    # discover all (for /news)
    python3.12 -m scripts.sync_committee_transcripts --committee LIBE --max 5
    python3.12 -m scripts.sync_committee_transcripts --committee LIBE --max 1 --transcribe
"""

import argparse
import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta
from typing import Optional

# Allow running as plain script from backend/ via `python3.12 scripts/sync_committee_transcripts.py`
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from core.database import SessionLocal
from models.committee_meeting_transcript import (
    CommitteeMeetingTranscript,
    TranscriptStatusEnum,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


SEED_TRANSCRIPT = {
    "committee_code": "LIBE",
    "title": "LIBE Committee Meeting - 17 April 2026 (seed test transcript)",
    "event_id": "libe-seed-20260417",
    "multimedia_url": "https://multimedia.europarl.europa.eu/en/webstreaming/libe-seed-20260417",
    "video_url": None,
    "transcript_text": (
        "Thank you Madam Chair. The Committee on Civil Liberties, Justice and Home Affairs opens "
        "the morning sitting of 17 April 2026. Our agenda today covers the extension of the "
        "temporary derogation from Directive 2002/58/EC under Regulation (EU) 2021/1232, "
        "procedure reference 2025/0429(COD). "
        "I give the floor to rapporteur Birgit Sippel. "
        "Thank you, Chair. Colleagues, as you know, the EP rejected the Commission's extension "
        "proposal in plenary on 26 March 2026 by 228 in favour, 311 against, 92 abstentions. "
        "The derogation expired on 3 April 2026. Our amended position -- adopted at plenary "
        "on 26 March 2026 as T10-0095/2026 -- proposes extension to 3 August 2027 with "
        "additional safeguards: mandatory judicial authorisation for any continued scanning, "
        "an obligation on providers to publish annual transparency reports specifying the number "
        "of false positives, and an explicit prohibition on client-side scanning. "
        "I yield the floor. "
        "The shadow rapporteurs have asked for the floor. Mr Agius Saliba on behalf of the S&D. "
        "Thank you Chair. We support the rapporteur's approach but would like to strengthen the "
        "language on age verification requirements in Article 3a. "
        "On behalf of the PfE, Mr Tanger Correa. We remain opposed to any extension without "
        "a full CJEU ruling on compatibility with Charter Articles 7 and 8. "
        "On behalf of the EPP, Mr Zarzalejos, who is also the permanent rapporteur on the CSA "
        "Regulation file, procedure 2022/0155(COD). We are reaching out to the Belgian "
        "presidency to accelerate the permanent regulation. "
        "On behalf of the Renew group, Ms Vautmans. Chair, the practical gap created by the "
        "expiry of the derogation on 3 April 2026 is serious. Providers like Discord and "
        "messaging platforms have no legal basis to scan for CSAM in number-independent "
        "interpersonal communications services. We need the extension to pass Council quickly. "
        "Exchange of views continues. The Committee will vote on the amendments at its "
        "next meeting. Meeting adjourned at 11:32."
    ),
    "transcript_segments": [
        {"start": 0.0, "end": 45.0, "text": "Opening remarks by the Chair."},
        {"start": 45.0, "end": 180.0, "text": "Rapporteur Sippel presentation."},
        {"start": 180.0, "end": 360.0, "text": "Shadow rapporteurs S&D and PfE."},
        {"start": 360.0, "end": 540.0, "text": "EPP shadow - Zarzalejos."},
        {"start": 540.0, "end": 720.0, "text": "Renew group - Vautmans on Discord/CSAM gap."},
        {"start": 720.0, "end": 810.0, "text": "Exchange of views and adjournment."},
    ],
    "word_count": 340,
    "duration_seconds": 810,
    "language": "EN",
    "agenda_items": [
        {
            "number": 1,
            "title": "Extension of CSAM temporary derogation 2025/0429(COD)",
            "procedure_refs": ["2025/0429(COD)"],
            "start_time": 45.0,
            "end_time": 720.0,
        },
    ],
    "related_procedure_refs": ["2025/0429(COD)", "2022/0155(COD)"],
    "speakers": [
        {"label": "Chair", "name": None, "group": None, "segments_count": 2},
        {"label": "Rapporteur", "name": "Birgit Sippel", "group": "S&D", "segments_count": 1},
        {"label": "Shadow", "name": "Alex Agius Saliba", "group": "S&D", "segments_count": 1},
        {"label": "Shadow", "name": "Antonio Tanger Correa", "group": "PfE", "segments_count": 1},
        {"label": "Shadow", "name": "Javier Zarzalejos", "group": "EPP", "segments_count": 1},
        {"label": "Shadow", "name": "Hilde Vautmans", "group": "Renew", "segments_count": 1},
    ],
    "speaker_count": 6,
    "status": TranscriptStatusEnum.COMPLETED,
    "transcription_cost": 0.0,
    "transcription_model": "seed-test-data",
    "transcribed_at": datetime.utcnow(),
}


def seed_test_data() -> int:
    session = SessionLocal()
    try:
        existing = session.query(CommitteeMeetingTranscript).filter_by(
            committee_code=SEED_TRANSCRIPT["committee_code"],
            event_id=SEED_TRANSCRIPT["event_id"],
        ).first()

        if existing:
            logger.info("[seed] Transcript already exists, updating status to completed")
            existing.status = TranscriptStatusEnum.COMPLETED
            existing.transcript_text = SEED_TRANSCRIPT["transcript_text"]
            existing.last_updated = datetime.utcnow()
            session.commit()
            return 0

        row = CommitteeMeetingTranscript(
            id=uuid.uuid4(),
            meeting_date=datetime(2026, 4, 17, 9, 30, 0),
            **SEED_TRANSCRIPT,
        )
        session.add(row)
        session.commit()
        logger.info(
            "[seed] Inserted seed transcript: %s %s (%d chars)",
            row.committee_code, row.meeting_date,
            len(row.transcript_text or ""),
        )
        return 0
    except Exception as exc:
        session.rollback()
        logger.error("[seed] Failed: %s", exc)
        return 1
    finally:
        session.close()


async def _enrich_video_url_if_missing(client, meeting) -> Optional[str]:
    """Fetch the detail page to extract the actual video URL if the listing doesn't expose one."""
    if meeting.video_url:
        return meeting.video_url
    if not meeting.multimedia_url:
        return None
    try:
        details = await client.get_meeting_details(meeting.multimedia_url)
        if details and details.get("video_url"):
            return details["video_url"]
    except Exception as exc:
        logger.debug("[discover] Detail-page fetch failed for %s: %s", meeting.multimedia_url, exc)
    return None


async def discover_meetings(
    committee: Optional[str] = None,
    max_meetings: int = 50,
    days: int = 30,
    do_transcribe: bool = False,
) -> int:
    """Discover committee meetings from the EP committees hub.

    Idempotent: inserts only meetings not already in the DB. Registers rows
    as PENDING with video_url (when available), ready for on-demand
    transcription triggered by the chatbot.
    """
    from services.api_clients.ep_multimedia_client import get_ep_multimedia_client
    from services.committee_transcription_service import get_committee_transcription_service

    client = get_ep_multimedia_client()

    date_from = (datetime.utcnow() - timedelta(days=days)).date()
    meetings = await client.discover_meetings(
        committee_code=committee, date_from=date_from,
    )
    meetings = meetings[:max_meetings]
    logger.info(
        "[discover] %d meetings found (committee=%s, since=%s)",
        len(meetings), committee or "all", date_from,
    )

    if not meetings:
        return 0

    session = SessionLocal()
    inserted = 0
    try:
        for meeting in meetings:
            existing = session.query(CommitteeMeetingTranscript).filter_by(
                committee_code=meeting.committee_code,
                event_id=meeting.event_id,
            ).first()
            if existing:
                # Backfill video_url if we've since discovered it
                if not existing.video_url and meeting.video_url:
                    existing.video_url = meeting.video_url
                    session.commit()
                continue

            # Try to enrich video URL from detail page
            video_url = await _enrich_video_url_if_missing(client, meeting)

            row = CommitteeMeetingTranscript(
                id=uuid.uuid4(),
                committee_code=meeting.committee_code,
                meeting_date=datetime.combine(meeting.meeting_date, datetime.min.time()),
                title=meeting.title,
                event_id=meeting.event_id,
                multimedia_url=meeting.multimedia_url,
                video_url=video_url,
                status=TranscriptStatusEnum.PENDING,
                agenda_items=[
                    {"number": ai.number, "title": ai.title, "procedure_refs": ai.procedure_refs}
                    for ai in meeting.agenda_items
                ],
            )
            session.add(row)
            session.commit()
            inserted += 1
            logger.info(
                "[discover] Registered PENDING: %s %s (video_url=%s)",
                row.committee_code, row.event_id, bool(video_url),
            )

            if do_transcribe and video_url:
                svc = get_committee_transcription_service()
                logger.info("[transcribe] Starting Whisper pipeline for %s", meeting.event_id)
                row.status = TranscriptStatusEnum.TRANSCRIBING
                session.commit()
                result = await svc.transcribe_meeting(
                    video_url=video_url,
                    committee_code=meeting.committee_code,
                    meeting_date=meeting.meeting_date,
                    title=meeting.title,
                    agenda_items=[
                        {"number": ai.number, "title": ai.title, "procedure_refs": ai.procedure_refs}
                        for ai in meeting.agenda_items
                    ],
                )
                for k, v in result.items():
                    if hasattr(row, k):
                        setattr(row, k, v)
                if result.get("status") == "completed":
                    row.transcribed_at = datetime.utcnow()
                session.commit()
                logger.info("[transcribe] Done: %s [%s]", meeting.event_id, row.status)

        logger.info("[discover] %d new meetings registered", inserted)
        return inserted
    except Exception as exc:
        session.rollback()
        logger.error("[discover] Failed: %s", exc)
        return 1
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="EP committee transcript sync")
    parser.add_argument("--seed-test-data", action="store_true",
                        help="Insert a synthetic seed transcript (no Whisper cost).")
    parser.add_argument("--committee", type=str, default=None,
                        help="Restrict to a single committee code (default: all).")
    parser.add_argument("--max", type=int, default=50,
                        help="Max meetings to process (default: 50).")
    parser.add_argument("--days", type=int, default=30,
                        help="Discover meetings from the last N days (default: 30).")
    parser.add_argument("--transcribe", action="store_true",
                        help="Also run Whisper transcription (costs ~$0.006/min).")
    args = parser.parse_args()

    if args.seed_test_data:
        sys.exit(seed_test_data())

    rc = asyncio.run(discover_meetings(
        committee=args.committee,
        max_meetings=args.max,
        days=args.days,
        do_transcribe=args.transcribe,
    ))
    sys.exit(0 if rc >= 0 else 1)


if __name__ == "__main__":
    main()
