"""
Seed EMA scientific-committee plenary meetings (CHMP, PRAC, COMP) for 2026 into
eu_calendar_events. This is the EFPIA-pitch differentiator: none of the rival
political-monitoring tools carry the EMA committee calendar.

These are GLOBAL calendar events (institution=EMA), so they enrich My EU Calendar
for every Yellow+ user, not just the EFPIA demo account.

Dates are authoritative, taken from the official EMA meeting-dates PDFs:
  CHMP: chmp-meeting-dates-2023-2024-2025-and-2026
  PRAC: prac-meetings-2025-and-2026
  COMP: committee-orphan-medicinal-products-comp-meetings-2025-2026-2027-2028
(PRAC/CHMP August plenaries are run by written procedure; still listed.)

Idempotent: skips any meeting whose external_id already exists.

Usage:
    cd backend && python3.12 scripts/seed_ema_committee_calendar.py            # dry-run
    cd backend && python3.12 scripts/seed_ema_committee_calendar.py --apply    # write DB
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from datetime import date

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

VENUE = "European Medicines Agency, Amsterdam"
ORGANISER = "European Medicines Agency (EMA)"

# (start_month, start_day, end_month, end_day) - all 2026.
COMMITTEES = {
    "CHMP": {
        "title": "CHMP plenary meeting",
        "url": "https://www.ema.europa.eu/en/committees/committee-medicinal-products-human-use-chmp",
        "policy_areas": ["Pharmaceutical Legislation", "Access to Medicines", "Public Health"],
        "description": (
            "Monthly plenary of the EMA Committee for Medicinal Products for Human Use (CHMP). "
            "Adopts opinions on marketing-authorisation applications, line extensions and safety "
            "referrals for human medicines, which the European Commission turns into EU-wide "
            "authorisations. The central decision point for EFPIA member companies' centrally "
            "authorised products."
        ),
        "dates": [
            (1, 26, 1, 29), (2, 23, 2, 26), (3, 23, 3, 26), (4, 20, 4, 23),
            (5, 18, 5, 21), (6, 22, 6, 25), (7, 20, 7, 23), (8, 17, 8, 20),
            (9, 14, 9, 17), (10, 12, 10, 15), (11, 9, 11, 12), (12, 7, 12, 10),
        ],
    },
    "PRAC": {
        "title": "PRAC plenary meeting",
        "url": "https://www.ema.europa.eu/en/committees/pharmacovigilance-risk-assessment-committee-prac",
        "policy_areas": ["Pharmacovigilance", "Pharmaceutical Legislation", "Public Health"],
        "description": (
            "Monthly plenary of the EMA Pharmacovigilance Risk Assessment Committee (PRAC). "
            "Assesses safety signals, periodic safety update reports, post-authorisation safety "
            "studies and referrals, and recommends risk-minimisation measures across the EU. "
            "Directly shapes the pharmacovigilance obligations of EFPIA member companies."
        ),
        "dates": [
            (1, 12, 1, 15), (2, 9, 2, 12), (3, 9, 3, 12), (4, 7, 4, 10),
            (5, 4, 5, 7), (6, 8, 6, 11), (7, 6, 7, 9), (8, 3, 8, 6),
            (8, 31, 9, 3), (9, 28, 10, 1), (10, 26, 10, 29), (11, 23, 11, 26),
        ],
    },
    "COMP": {
        "title": "COMP plenary meeting",
        "url": "https://www.ema.europa.eu/en/committees/committee-orphan-medicinal-products-comp",
        "policy_areas": ["Rare and Orphan Diseases", "Pharmaceutical Legislation", "Access to Medicines"],
        "description": (
            "Plenary of the EMA Committee for Orphan Medicinal Products (COMP). Reviews orphan "
            "designation applications and advises on the EU orphan-medicines framework. Relevant "
            "to EFPIA's rare-disease files and to the orphan-incentive debate in the pharmaceutical "
            "legislation revision."
        ),
        "dates": [
            (1, 20, 1, 22), (2, 17, 2, 19), (3, 17, 3, 19), (4, 14, 4, 16),
            (5, 11, 5, 13), (6, 16, 6, 18), (7, 14, 7, 16), (9, 8, 9, 10),
            (10, 6, 10, 8), (11, 3, 11, 5), (12, 1, 12, 3),
        ],
    },
}

INSERT_SQL = text(
    """
    INSERT INTO eu_calendar_events (
        id, institution, event_type, title, description,
        start_date, end_date, all_day,
        policy_areas, status, source_url, source, external_id,
        organiser, venue, scraped_at, first_seen, last_updated
    ) VALUES (
        :id, 'EMA', 'committee_meeting', :title, :description,
        :start_date, :end_date, true,
        CAST(:policy_areas AS text[]), 'scheduled', :source_url, 'ema_committee', :external_id,
        :organiser, :venue, NOW(), NOW(), NOW()
    )
    """
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    apply = args.apply

    logger.info("=" * 78)
    logger.info(f"Seed EMA committee calendar 2026 (CHMP/PRAC/COMP) - {'APPLY' if apply else 'DRY RUN'}")
    logger.info("=" * 78)

    db = SessionLocal()
    created = skipped = 0
    try:
        for code, spec in COMMITTEES.items():
            for i, (sm, sd, em, ed) in enumerate(spec["dates"], start=1):
                external_id = f"ema-{code.lower()}-2026-m{i:02d}"
                exists = db.execute(
                    text("SELECT 1 FROM eu_calendar_events WHERE external_id = :x"),
                    {"x": external_id},
                ).first()
                if exists:
                    skipped += 1
                    continue
                params = {
                    "id": str(uuid.uuid4()),
                    "title": spec["title"],
                    "description": spec["description"],
                    "start_date": date(2026, sm, sd),
                    "end_date": date(2026, em, ed),
                    "policy_areas": "{" + ",".join(spec["policy_areas"]) + "}",
                    "source_url": spec["url"],
                    "external_id": external_id,
                    "organiser": ORGANISER,
                    "venue": VENUE,
                }
                if apply:
                    db.execute(INSERT_SQL, params)
                    created += 1
                    logger.info(f"  [event] CREATE {external_id}  {params['start_date']}–{params['end_date']}")
                else:
                    created += 1
                    logger.info(f"  [event] WOULD CREATE {external_id}  {params['start_date']}–{params['end_date']}")

        if apply:
            db.commit()
            logger.info(f"\n[OK] committed. created={created}, skipped(existing)={skipped}")
        else:
            db.rollback()
            logger.info(f"\n[OK] dry-run. would_create={created}, skipped(existing)={skipped}")
    except Exception as e:
        db.rollback()
        logger.exception(f"FAILED: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
