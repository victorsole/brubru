"""
EP Committee Meeting Transcripts -- sync CLI.

Discovery is the DEFAULT mode (safe to run from /news morning routine).
Transcription is opt-in via --transcribe (costs ~$0.006/min via Whisper).

Modes:

  1. (default) `--discover [--committee LIBE] [--max 50] [--days 30]`
                          -> scrape the EP committees hub
                             (europarl.europa.eu/committees/en/meetings/webstreaming),
                             insert PENDING rows with video_url. Idempotent.

  2. `... --transcribe`   -> ALSO run Whisper on any newly-discovered rows.
                             Intended for scheduled batch, not /news.

Usage:
    python3.12 -m scripts.sync_committee_transcripts                    # discover all (for /news)
    python3.12 -m scripts.sync_committee_transcripts --committee LIBE --max 5
    python3.12 -m scripts.sync_committee_transcripts --committee LIBE --max 1 --transcribe

Note: The --seed-test-data flag was removed on 28 April 2026 after the
fabricated-transcript incident (22 April + recurrence on 27 April). Seed/test
fixtures must not live in production scripts. If a wiring test is needed,
write a fixture into a tests/ directory with an `is_test=True` row marker.
"""

import argparse
import asyncio
import logging
import os
import sys
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


# NOTE (28 April 2026): The SEED_TRANSCRIPT constant and seed_test_data() function
# were removed in this file after the fabricated-transcript incident. They contained
# a synthetic LIBE transcript with named-MEP rapporteur, fabricated PE/A/T identifiers,
# and a fabricated vote tally. Even though the function was gated behind --seed-test-data,
# the *file itself* was being grepped by the model when reasoning about LIBE / 2025/0429(COD),
# and the warning text in ai_service.py named the same identifiers verbatim. The combination
# of those two things re-anchored the model on the fake values. Test fixtures of this kind
# must live under tests/, NOT in production scripts -- and any committee_meeting_transcripts
# row used for testing must carry an explicit is_test=True marker filterable at query time.


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
    parser.add_argument("--committee", type=str, default=None,
                        help="Restrict to a single committee code (default: all).")
    parser.add_argument("--max", type=int, default=50,
                        help="Max meetings to process (default: 50).")
    parser.add_argument("--days", type=int, default=30,
                        help="Discover meetings from the last N days (default: 30).")
    parser.add_argument("--transcribe", action="store_true",
                        help="Also run Whisper transcription (costs ~$0.006/min).")
    args = parser.parse_args()

    rc = asyncio.run(discover_meetings(
        committee=args.committee,
        max_meetings=args.max,
        days=args.days,
        do_transcribe=args.transcribe,
    ))
    sys.exit(0 if rc >= 0 else 1)


if __name__ == "__main__":
    main()
