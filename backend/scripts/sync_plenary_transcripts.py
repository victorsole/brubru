"""
Ingest EP plenary debates as per-debate transcript rows from the official CRE
verbatim (text — speaker-attributed, multilingual; NO ASR cost). One row per
debate (institution='EP', committee_code='PLENARY'), so each agenda item is a
focused, browsable card with its own procedure refs.

Discovers candidate sitting dates from eu_calendar_events (plenary), fetches CRE
via the WAF browser client (with retry), and commits PER DEBATE (so one bad
debate never rolls back a whole sitting). Idempotent via event_id.

Usage:
    python3.12 -m scripts.sync_plenary_transcripts --since 2026-01-01 --limit 40
    python3.12 -m scripts.sync_plenary_transcripts --date 2026-05-18
"""

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, date as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from sqlalchemy import text as sqltext
from core.database import SessionLocal
from models.committee_meeting_transcript import CommitteeMeetingTranscript as CMT, TranscriptStatusEnum
from services.api_clients.cre_client import CREClient


def _debate_text(deb) -> str:
    out = []
    for sp in deb.speakers:
        who = sp.name or "Speaker"
        tag = sp.role or sp.political_group or ("EU institution" if sp.is_institutional else "")
        head = f"{who} ({tag})" if tag else who
        txt = (sp.text or "").strip()
        if txt:
            out.append(f"{head}: {txt}")
    return "\n\n".join(out)


async def _fetch(cre, dd, tries=3):
    for _ in range(tries):
        try:
            s = await cre.fetch_session(dd)
            if s and s.debate_count > 0:
                return s
        except Exception:
            pass
        await asyncio.sleep(2)
    return None


async def run(dates):
    cre = CREClient()
    total = 0
    for dd in dates:
        s = await _fetch(cre, dd)
        if not s:
            print(f"  {dd} no sitting")
            continue
        n = 0
        for deb in s.debates:
            if not deb.speakers:
                continue
            body = _debate_text(deb)
            if len(body) < 150:
                continue
            eid = f"plenary-{dd.isoformat()}-ch{deb.chapter_number}"
            db = SessionLocal()
            try:
                if db.query(CMT.id).filter(CMT.event_id == eid).first():
                    continue
                db.add(CMT(
                    id=uuid.uuid4(), institution="EP", committee_code="PLENARY",
                    meeting_date=datetime(dd.year, dd.month, dd.day),
                    title=f"Plenary — {(deb.title or 'debate').strip()[:470]}",
                    transcript_text=body, word_count=len(body.split()),
                    speaker_count=deb.speaker_count,
                    related_procedure_refs=(deb.procedure_refs or [])[:20],
                    status=TranscriptStatusEnum.COMPLETED, transcription_model="ep-cre-verbatim",
                    language="EN", multimedia_url=s.source_url, event_id=eid,
                    transcribed_at=datetime.utcnow(),
                ))
                db.commit(); n += 1
            except Exception as e:
                db.rollback(); print(f"    {eid} ERR {str(e)[:80]}")
            finally:
                db.close()
        total += n
        print(f"  {dd} -> {n} debate rows")
    print(f"[plenary] DONE added={total}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", type=str, help="Single sitting date YYYY-MM-DD")
    ap.add_argument("--since", type=str, default="2026-01-01")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()

    if args.date:
        y, m, d = map(int, args.date.split("-"))
        dates = [D(y, m, d)]
    else:
        db = SessionLocal()
        rows = db.execute(sqltext("""
            SELECT DISTINCT start_date FROM eu_calendar_events
            WHERE institution='EP' AND (ep_activity_type='plenary_session' OR event_type='plenary_session')
              AND start_date <= CURRENT_DATE AND start_date >= :since
            ORDER BY start_date DESC LIMIT :lim
        """), {"since": args.since, "lim": args.limit}).fetchall()
        db.close()
        dates = [(r[0].date() if hasattr(r[0], "date") else r[0]) for r in rows]
    print(f"[plenary] {len(dates)} candidate date(s)")
    asyncio.run(run(dates))


if __name__ == "__main__":
    main()
