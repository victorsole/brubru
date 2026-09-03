"""
Prune the EFPIA demo account's TED tender matches down to health-relevant only.

The TenderMatcher is sector-blind for TED procurement (neutral eu_wide/value
scores let ~80% of all tenders clear the 35.0 threshold), so a freshly matched
health profile ends up "matching" bulldozer repairs and insurance contracts.
For the 28 May 2026 EFPIA demo we keep only the genuinely health-relevant TED
matches (CPV 33 medical/pharma, 85 health & social work, 73 R&D, or a health
keyword in the title). F&T proposals are scored on-the-fly from the profile
keywords and are unaffected by this prune.

Usage:
    cd backend && python3.12 scripts/prune_efpia_tenderator_to_health.py            # dry-run
    cd backend && python3.12 scripts/prune_efpia_tenderator_to_health.py --apply    # write DB
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

DEMO_EMAIL = "public-affairs@efpia.eu"

HEALTH_FILTER = """
    t.cpv_main LIKE '33%' OR t.cpv_main LIKE '85%' OR t.cpv_main LIKE '73%'
    OR array_to_string(t.cpv_codes, ',') ~ '(^|,)(33|85|73)'
    OR t.title ILIKE ANY(ARRAY[
        '%health%','%medic%','%pharma%','%clinical%','%hospital%','%vaccin%',
        '%cancer%','%disease%','%patient%','%therap%','%surg%','%nurs%',
        '%biomed%','%diagnos%','%laborator%'
    ])
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    apply = args.apply

    logger.info("=" * 78)
    logger.info(f"Prune EFPIA demo Tenderator matches to health - {'APPLY' if apply else 'DRY RUN'}")
    logger.info("=" * 78)

    db = SessionLocal()
    try:
        profile_id = db.execute(
            text(
                "SELECT tp.id FROM tender_profiles tp JOIN users u ON u.id=tp.user_id "
                "WHERE u.email=:e"
            ),
            {"e": DEMO_EMAIL},
        ).scalar()
        if profile_id is None:
            raise RuntimeError(f"No tender_profiles row for {DEMO_EMAIL}.")

        total = db.execute(
            text("SELECT count(*) FROM tender_matches WHERE profile_id=:p"), {"p": profile_id}
        ).scalar()
        keep = db.execute(
            text(
                f"SELECT count(*) FROM tender_matches tm JOIN tenders t ON t.id=tm.tender_id "
                f"WHERE tm.profile_id=:p AND ({HEALTH_FILTER})"
            ),
            {"p": profile_id},
        ).scalar()
        logger.info(f"  [profile {profile_id}] total matches={total}, health keep={keep}, "
                    f"to delete={total - keep}")

        if apply:
            res = db.execute(
                text(
                    f"DELETE FROM tender_matches WHERE profile_id=:p AND tender_id NOT IN "
                    f"(SELECT t.id FROM tenders t WHERE ({HEALTH_FILTER}))"
                ),
                {"p": profile_id},
            )
            db.commit()
            remaining = db.execute(
                text("SELECT count(*) FROM tender_matches WHERE profile_id=:p"), {"p": profile_id}
            ).scalar()
            logger.info(f"  [delete] removed {res.rowcount} non-health matches; {remaining} remain")
            logger.info("\n[OK] committed.")
        else:
            logger.info("\n[OK] dry-run only. Re-run with --apply to commit.")
    except Exception as e:
        db.rollback()
        logger.exception(f"FAILED: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
