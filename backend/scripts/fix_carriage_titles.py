"""
Fix junk / placeholder legislative_carriages titles surfaced in the Amendator
tracked-files loader:
  - 2023/0131(COD): "Revision of EU pharmaceutical legislation" -> "... (Regulation)"
  - 2023/0132(COD): "Procedure File: 2023/0132(COD)"             -> "... (Directive)"
  - 52025PC1022:    "CELEX:52025PC1022(01): Proposal for a REGULATION ..." -> "European Biotech Act"

These are global carriage titles, so the cleanup applies everywhere the carriage
is shown (My Files, Tracker, Amendator, chat).

Usage:
    cd backend && python3.12 scripts/fix_carriage_titles.py            # dry-run
    cd backend && python3.12 scripts/fix_carriage_titles.py --apply
"""
from __future__ import annotations

import pathlib

# Repo root derived from this file's location, so a repo move cannot break the script.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])


import argparse
import logging
import sys

sys.path.insert(0, f"{_REPO_ROOT}/backend")
sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import text
from dotenv import load_dotenv
load_dotenv(f"{_REPO_ROOT}/.env")
from core.database import SessionLocal, engine

engine.echo = False
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
for noisy in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

# carriage id -> new title
UPDATES = {
    "e83253e6-d3f4-4d3d-a781-64d8ce5e2084": "Revision of EU pharmaceutical legislation (Regulation)",
    "e17cfd3b-4a3f-4599-a0d8-07575825223a": "Revision of EU pharmaceutical legislation (Directive)",
    "c1f4698a-0f80-4d93-9ad2-7a33afb97fb7": "European Biotech Act",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    apply = args.apply

    db = SessionLocal()
    try:
        for cid, new_title in UPDATES.items():
            row = db.execute(
                text("SELECT left(title,70) FROM legislative_carriages WHERE id=:i"), {"i": cid}
            ).first()
            if not row:
                logger.warning(f"  [skip] {cid[:8]} not found")
                continue
            logger.info(f"  [{cid[:8]}] OLD: {row[0]}")
            logger.info(f"            NEW: {new_title}")
            if apply:
                db.execute(
                    text("UPDATE legislative_carriages SET title=:t, last_updated=NOW() WHERE id=:i"),
                    {"t": new_title, "i": cid},
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
