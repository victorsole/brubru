"""
Discover recent Commission (EbS) recordings and register them as PENDING
committee_meeting_transcripts rows (institution='EC'), so they appear in MEUB
Transcripts as on-demand-transcribable items. NO ASR here (that's on-demand).

Usage:
    python3.12 -m scripts.sync_ebs_transcripts --limit 30
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
from services.api_clients.ebs_client import discover_recent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args()

    recs = discover_recent(limit=args.limit)
    print(f"[ebs] discovered {len(recs)} recordings with audio")
    db = SessionLocal()
    added = skipped = 0
    try:
        for r in recs:
            if not r.get("meeting_date"):
                skipped += 1
                continue
            exists = db.query(CMT.id).filter(CMT.event_id == r["external_id"]).first()
            if exists:
                skipped += 1
                continue
            db.add(CMT(
                id=uuid.uuid4(),
                institution="EC",
                committee_code="EC",
                meeting_date=r["meeting_date"],
                title=r["title"],
                video_url=r["audio_url"],
                multimedia_url=r.get("multimedia_url"),
                event_id=r["external_id"],
                language="EN",
                duration_seconds=r.get("duration_seconds"),
                status=TranscriptStatusEnum.PENDING,
            ))
            added += 1
        db.commit()
    finally:
        db.close()
    print(f"[ebs] added={added} skipped={skipped}")


if __name__ == "__main__":
    main()
