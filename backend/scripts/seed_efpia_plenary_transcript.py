"""
Seed a REAL EP plenary debate transcript into the EFPIA demo account's MEUB
Documents, so EFPIA sees that Brubru delivers verbatim plenary transcripts.

Fetches the official CRE (Compte Rendu in Extenso) for a plenary sitting via the
WAF-clearing browser path, parses it (speaker name + political group + full
speech text), picks a substantive debate (health-related if present, else the
one with the most speakers), and stores it as a user_document.

Usage:
    cd backend && python3.12 scripts/seed_efpia_plenary_transcript.py            # dry-run (fetch + show)
    cd backend && python3.12 scripts/seed_efpia_plenary_transcript.py --apply
"""
from __future__ import annotations

import argparse
import datetime
import json
import logging
import sys
import uuid

sys.path.insert(0, "/Users/victorsole/Documents/GitHub/brubru/backend")
sys.path.insert(0, "/Users/victorsole/Documents/GitHub/brubru")

from sqlalchemy import text
from dotenv import load_dotenv
load_dotenv("/Users/victorsole/Documents/GitHub/brubru/.env")
from core.database import SessionLocal, engine
from services.api_clients.cre_client import get_cre_client

engine.echo = False
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
for n in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    logging.getLogger(n).setLevel(logging.WARNING)

DEMO_EMAIL = "public-affairs@efpia.eu"
SESSION_DATE = datetime.date(2026, 5, 18)
HEALTH_KW = ("health", "medic", "pharma", "cancer", "clinical", "vaccin", "disease", "patient", "care")
MAX_CHARS = 45000


def choose_debate(session):
    substantive = [d for d in session.debates if d.speaker_count >= 2]
    health = [d for d in substantive if any(k in (d.title or "").lower() for k in HEALTH_KW)]
    pool = health or substantive
    if not pool:
        return None
    return max(pool, key=lambda d: d.speaker_count)


def build_transcript(debate, session) -> str:
    lines = [
        f"# EP plenary debate — {SESSION_DATE.strftime('%d %B %Y')}",
        f"## {debate.title}",
        "",
        f"_Official verbatim record (Compte Rendu in Extenso) of the European Parliament plenary sitting. Source: {session.source_url}_",
        "",
    ]
    for sp in debate.speakers:
        grp = f" ({sp.group})" if getattr(sp, "group", None) else ""
        name = sp.name or "Speaker"
        speech = (sp.text or "").strip()
        if not speech:
            continue
        lines.append(f"**{name}{grp}.** {speech}")
        lines.append("")
    body = "\n".join(lines)
    return body[:MAX_CHARS]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    c = get_cre_client()
    url = c._build_url(SESSION_DATE, "EN")
    logger.info(f"Fetching CRE via browser: {url}")
    xml = c._fetch_xml_via_browser(url)
    if not xml or "<CHAPTER" not in xml:
        logger.error("No CRE content fetched."); sys.exit(1)
    session = c._parse_session(xml, SESSION_DATE, url)
    logger.info(f"Parsed {session.debate_count} debates, {session.total_speakers} speakers")

    debate = choose_debate(session)
    if not debate:
        logger.error("No substantive debate found."); sys.exit(1)
    logger.info(f"Chosen debate: {debate.title!r} ({debate.speaker_count} speakers)")

    content = build_transcript(debate, session)
    title = f"EP plenary debate transcript — 18 May 2026 — {debate.title[:70]}"
    logger.info(f"Document title: {title}")
    logger.info(f"Transcript length: {len(content):,} chars")

    db = SessionLocal()
    try:
        uid = db.execute(text("SELECT id::text FROM users WHERE email=:e"), {"e": DEMO_EMAIL}).scalar()
        if not uid:
            raise RuntimeError(f"Demo user {DEMO_EMAIL} not found")
        exists = db.execute(text("SELECT 1 FROM user_documents WHERE user_id=:u AND title=:t"),
                            {"u": uid, "t": title}).first()
        if exists:
            logger.info("  [doc] SKIP (already present)")
        elif args.apply:
            meta = {"original_document_type": "transcript", "source": "ep_cre_verbatim",
                    "session_date": "2026-05-18", "source_url": url}
            db.execute(text("""
                INSERT INTO user_documents (id, user_id, document_type, title, content,
                    policy_areas, tags, executive_summary, doc_metadata,
                    include_in_ai_context, is_private, version, view_count, is_featured,
                    created_at, updated_at)
                VALUES (:id,:u,'note',:title,:content, :areas,:tags,:exec,CAST(:meta AS jsonb),
                    true,true,1,0,false,NOW(),NOW())
            """), {
                "id": str(uuid.uuid4()), "u": uid, "title": title, "content": content,
                "areas": ["Public Health", "Pharmaceutical Legislation"],
                "tags": ["ep-plenary", "transcript", "verbatim", "cre"],
                "exec": f"Verbatim transcript of the European Parliament plenary debate '{debate.title}' on 18 May 2026 ({debate.speaker_count} speakers), from the official CRE record.",
                "meta": json.dumps(meta),
            })
            from scripts._validate_user_documents import validate_user_documents_for
            validate_user_documents_for(db, uid)
            db.commit()
            logger.info("  [doc] CREATE committed.")
        else:
            logger.info("  [doc] dry-run (use --apply to write)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
