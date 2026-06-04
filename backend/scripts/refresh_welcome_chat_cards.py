"""
Refresh the chat welcome-grid example prompts (the first 3 main_chat prompts
shown as the EP Plenary / Ask anything / Policy intelligence cards).

Sort 5 + 6 were stale and code-heavy (DMA Review COM(2026) 178; Cybersecurity
Act 2 / ENISA 2026/0011 COD) which also break the no-institutional-codes-in-hero
rule. Replace with fresh, plain-language, KB-answerable, health-relevant queries.
Sort 8 (also pharma reform) is repointed to avoid duplicating the new sort 5.

Usage:
    cd backend && python3.12 scripts/refresh_welcome_chat_cards.py --apply
"""
from __future__ import annotations

import argparse, logging, sys
sys.path.insert(0, "/Users/victorsole/Documents/GitHub/brubru/backend")
sys.path.insert(0, "/Users/victorsole/Documents/GitHub/brubru")
from sqlalchemy import text
from dotenv import load_dotenv
load_dotenv("/Users/victorsole/Documents/GitHub/brubru/.env")
from core.database import SessionLocal, engine

engine.echo = False
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
for n in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    logging.getLogger(n).setLevel(logging.WARNING)

UPDATES = {
    # sort 5 (EP Plenary card)
    "c1e834e3-5cbe-4238-bbd2-2b9c565673f3":
        "What is the EU pharmaceutical legislation revision, and what are the main points of contention?",
    # sort 6 (Ask anything card)
    "0ec4eb2b-cf2f-48a6-828b-579a4a2845a0":
        "What is the EU Health Technology Assessment Regulation and how does it work?",
    # sort 8 (not in welcome grid) — repoint so it does not duplicate the new sort 5
    "e11d4b27-3f4e-4925-a766-1c797170078c":
        "What is on the agenda for the next European Parliament plenary session?",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    db = SessionLocal()
    try:
        for cid, new_text in UPDATES.items():
            old = db.execute(text("SELECT left(text,70) FROM chat_example_prompts WHERE id=:i"), {"i": cid}).scalar()
            if old is None:
                logger.warning(f"  [skip] {cid[:8]} not found"); continue
            logger.info(f"  [{cid[:8]}] OLD: {old}")
            logger.info(f"            NEW: {new_text}")
            if args.apply:
                db.execute(text("UPDATE chat_example_prompts SET text=:t, updated_at=NOW() WHERE id=:i"),
                           {"t": new_text, "i": cid})
        if args.apply:
            db.commit(); logger.info("\n[OK] committed.")
        else:
            db.rollback(); logger.info("\n[OK] dry-run.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
