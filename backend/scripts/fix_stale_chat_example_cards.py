"""
Refresh the two stale, past-dated chat example cards on the main chat landing.

Both referenced specific past dates (the "Wednesday 6 May 2026 College agenda"
card and the "GCOT on 4 May 2026" card) which read as outdated on 27 May. Replace
with current, evergreen, health-relevant queries (EFPIA demo + general users).

Usage:
    cd backend && python3.12 scripts/fix_stale_chat_example_cards.py            # dry-run
    cd backend && python3.12 scripts/fix_stale_chat_example_cards.py --apply
"""
from __future__ import annotations

import argparse
import logging
import sys

sys.path.insert(0, "/Users/victorsole/Documents/GitHub/brubru/backend")
sys.path.insert(0, "/Users/victorsole/Documents/GitHub/brubru")

from sqlalchemy import text
from dotenv import load_dotenv
load_dotenv("/Users/victorsole/Documents/GitHub/brubru/.env")
from core.database import SessionLocal, engine

engine.echo = False
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
for noisy in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

UPDATES = {
    # id : new evergreen text
    "335b8f63-f217-40a3-9dc0-79103eed8de2":
        "What stage is the Critical Medicines Act at, and who is its rapporteur?",
    "e11d4b27-3f4e-4925-a766-1c797170078c":
        "What is the EU pharmaceutical legislation revision, and what are the main points of contention?",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    apply = args.apply

    db = SessionLocal()
    try:
        for cid, new_text in UPDATES.items():
            row = db.execute(
                text("SELECT left(text,70) FROM chat_example_prompts WHERE id=:i"), {"i": cid}
            ).first()
            if not row:
                logger.warning(f"  [skip] {cid[:8]} not found")
                continue
            logger.info(f"  [{cid[:8]}] OLD: {row[0]}")
            logger.info(f"            NEW: {new_text}")
            if apply:
                db.execute(
                    text("UPDATE chat_example_prompts SET text=:t, updated_at=NOW() WHERE id=:i"),
                    {"t": new_text, "i": cid},
                )
        if apply:
            db.commit()
            logger.info("\n[OK] committed.")
        else:
            db.rollback()
            logger.info("\n[OK] dry-run. Re-run with --apply.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
