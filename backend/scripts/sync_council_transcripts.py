"""
Discover recent Council (tvnewsroom) recordings and register them as PENDING
committee_meeting_transcripts rows (institution='COUNCIL'), transcribable on demand
in MEUB Transcripts. NO ASR here.

Usage:
    python3.12 -m scripts.sync_council_transcripts --limit 25
"""

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from core.database import SessionLocal
from models.committee_meeting_transcript import CommitteeMeetingTranscript as CMT, TranscriptStatusEnum
from services.api_clients.council_client import discover_recent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args()

    recs = discover_recent(limit=args.limit)
    print(f"[council] discovered {len(recs)} recordings with audio")
    db = SessionLocal()
    added = skipped = 0
    try:
        for r in recs:
            if not r.get("meeting_date"):
                skipped += 1
                continue
            if db.query(CMT.id).filter(CMT.event_id == r["external_id"]).first():
                skipped += 1
                continue
            db.add(CMT(
                id=uuid.uuid4(),
                institution="COUNCIL",
                committee_code="COUNCIL",
                meeting_date=r["meeting_date"],
                title=r["title"],
                video_url=r["audio_url"],
                multimedia_url=r.get("multimedia_url"),
                event_id=r["external_id"],
                language="EN",
                status=TranscriptStatusEnum.PENDING,
            ))
            added += 1
        db.commit()
    finally:
        db.close()
    print(f"[council] added={added} skipped={skipped}")


if __name__ == "__main__":
    main()
