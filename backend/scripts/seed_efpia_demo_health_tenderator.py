"""
Finalise the EFPIA demo account (public-affairs@efpia.eu) for the 28 May 2026 pitch:

  1. Rename the user to just "EFPIA" (full_name / first_name / preferred_name),
     so the product greets the user as "EFPIA".
  2. Set health-only policy interests.
  3. Create a health-focused Tenderator profile (clears the setup wizard and
     drives matching), then run the real matcher to populate TED matches.

Why this surfaces health "tenders AND proposals" from EU Funds & Tenders:
  - The matcher persists TED (tenders) matches against the profile.
  - The unified-feed "Matches" view scores F&T proposals (ft_calls_for_proposals)
    on-the-fly from the profile KEYWORDS, and F&T tenders from CPV + keywords.
    A rich health keyword + CPV set therefore lights up all three buckets
    (99 health proposals + health TED tenders + health F&T tenders are already
    in the global pool).

Usage:
    cd backend && python3.12 scripts/seed_efpia_demo_health_tenderator.py            # dry-run
    cd backend && python3.12 scripts/seed_efpia_demo_health_tenderator.py --apply    # write DB
"""

from __future__ import annotations

import pathlib

# Repo root derived from this file's location, so a repo move cannot break the script.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])


import argparse
import asyncio
import json
import logging
import sys

sys.path.insert(0, f"{_REPO_ROOT}/backend")
sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv(f"{_REPO_ROOT}/.env")

from core.database import SessionLocal, engine
from models.tender import TenderProfile, TenderMatch
from services.tenders.matcher import TenderMatcher

engine.echo = False
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
for noisy in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

DEMO_EMAIL = "public-affairs@efpia.eu"

HEALTH_POLICY_INTERESTS = [
    "Public Health",
    "Pharmaceutical Legislation",
    "Access to Medicines",
    "Health Technology Assessment (HTA)",
    "Clinical Trials",
    "Antimicrobial Resistance (AMR)",
    "Critical Medicines and Shortages",
    "Vaccines",
    "Oncology and Cancer Policy",
    "Rare and Orphan Diseases",
    "Medical Devices",
    "European Health Data Space",
    "Biotechnology and Life Sciences",
    "Pharmaceutical IP and Incentives",
]

# 2-digit CPV families: 33 medical/pharma, 85 health & social services, 73 R&D.
HEALTH_CPV_CATEGORIES = ["33", "85", "73"]
HEALTH_CPV_CODES = [
    "33000000",  # Medical equipments, pharmaceuticals and personal care products
    "33600000",  # Pharmaceutical products
    "33690000",  # Various medicinal products
    "33141000",  # Disposable non-chemical medical consumables
    "85000000",  # Health and social work services
    "85100000",  # Health services
    "73000000",  # Research and development services
    "73100000",  # Research and experimental development services
]
HEALTH_KEYWORDS = [
    "health", "healthcare", "medical", "medicine", "medicines", "pharmaceutical",
    "pharma", "clinical", "clinical trial", "clinical trials", "vaccine", "vaccines",
    "vaccination", "antimicrobial", "antimicrobial resistance", "AMR", "antibiotic",
    "oncology", "cancer", "rare disease", "orphan", "HTA", "health technology assessment",
    "biotech", "biotechnology", "public health", "life sciences", "disease", "patient",
    "therapy", "therapeutic", "drug", "health data", "mental health", "chronic disease",
    "pandemic", "epidemic", "diagnostics", "medical device", "EHDS", "one health",
]

COMPANY_NAME = "EFPIA (European Federation of Pharmaceutical Industries and Associations)"
SECTORS_DESCRIPTION = (
    "Research-based pharmaceutical industry and public health: pharmaceutical innovation, "
    "access to medicines, clinical trials, vaccines, antimicrobial resistance, oncology, "
    "rare and orphan diseases, health technology assessment, medical devices, biotechnology "
    "and the European Health Data Space."
)


def rename_and_set_interests(db, apply: bool) -> str:
    row = db.execute(
        text("SELECT id::text, full_name FROM users WHERE email=:e"), {"e": DEMO_EMAIL}
    ).first()
    if not row:
        raise RuntimeError(f"Demo user {DEMO_EMAIL} not found. Run seed_efpia_public_affairs_demo.py --apply first.")
    user_id, current_name = row.id, row.full_name
    logger.info(f"  [user] {DEMO_EMAIL} (id={user_id[:8]}, current name={current_name!r})")
    if apply:
        db.execute(
            text(
                "UPDATE users SET full_name='EFPIA', first_name='EFPIA', preferred_name='EFPIA',"
                " policy_interests=:pi, updated_at=NOW() WHERE email=:e"
            ),
            {"pi": json.dumps(HEALTH_POLICY_INTERESTS), "e": DEMO_EMAIL},
        )
        logger.info("  [user] -> name='EFPIA', health policy interests set "
                    f"({len(HEALTH_POLICY_INTERESTS)} items)")
    else:
        logger.info("  [user] WOULD set name='EFPIA' + "
                    f"{len(HEALTH_POLICY_INTERESTS)} health policy interests")
    return user_id


def create_profile(db, user_id: str, apply: bool):
    existing = db.query(TenderProfile).filter(TenderProfile.user_id == user_id).first()
    if existing:
        logger.info(f"  [profile] EXISTS (id={existing.id}) - updating health criteria")
        if apply:
            existing.company_name = COMPANY_NAME
            existing.cpv_categories = HEALTH_CPV_CATEGORIES
            existing.cpv_codes = HEALTH_CPV_CODES
            existing.sectors_description = SECTORS_DESCRIPTION
            existing.keywords = HEALTH_KEYWORDS
            existing.eu_wide = True
            existing.min_deadline_days = 0
            existing.is_active = True
            db.commit()
            db.refresh(existing)
        return existing
    if not apply:
        logger.info("  [profile] WOULD CREATE health Tenderator profile "
                    f"(cpv={HEALTH_CPV_CATEGORIES}, {len(HEALTH_KEYWORDS)} keywords)")
        return None
    prof = TenderProfile(
        user_id=user_id,
        company_name=COMPANY_NAME,
        cpv_categories=HEALTH_CPV_CATEGORIES,
        cpv_codes=HEALTH_CPV_CODES,
        sectors_description=SECTORS_DESCRIPTION,
        eu_wide=True,
        keywords=HEALTH_KEYWORDS,
        min_deadline_days=0,
        is_active=True,
    )
    db.add(prof)
    db.commit()
    db.refresh(prof)
    logger.info(f"  [profile] CREATE health Tenderator profile (id={prof.id})")
    return prof


def run_matching(db, profile_id: int):
    """Replicates api.tenderator.run_profile_matching_background persistence."""
    matcher = TenderMatcher(db, score_threshold=35.0)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        results = loop.run_until_complete(matcher.match_single_profile(profile_id))
    finally:
        loop.close()
    created = 0
    for r in results:
        exists = db.query(TenderMatch).filter(
            TenderMatch.profile_id == r.profile_id, TenderMatch.tender_id == r.tender_id
        ).first()
        if exists:
            continue
        db.add(TenderMatch(
            tender_id=r.tender_id,
            profile_id=r.profile_id,
            user_id=r.user_id,
            match_score=r.total_score,
            match_reasons=r.score_breakdown,
            match_details=r.match_details,
        ))
        created += 1
    db.commit()
    logger.info(f"  [match] {created} new TED tender matches created for profile {profile_id}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    apply = args.apply

    logger.info("=" * 78)
    logger.info(f"EFPIA demo: rename + health interests + Tenderator - {'APPLY' if apply else 'DRY RUN'}")
    logger.info("=" * 78)

    db = SessionLocal()
    try:
        user_id = rename_and_set_interests(db, apply)
        prof = create_profile(db, user_id, apply)
        if apply and prof is not None:
            run_matching(db, prof.id)
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
