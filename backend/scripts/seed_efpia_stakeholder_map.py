"""
Add a curated "Stakeholder map" document to the EFPIA demo account
(public-affairs@efpia.eu) Documents tab, built from Brubru's EU officials data
(/api/v1/officials). Health-first: the Health Commissioner, the Council Health
configuration (one minister per Member State, which maps onto EFPIA's national
associations), the Parliament health committees, and the EMA.

Counters the incumbent monitoring tools' "stakeholder management" feature: every
named official is a real row in Brubru and is queryable in chat by slug.

Usage:
    cd backend && python3.12 scripts/seed_efpia_stakeholder_map.py            # dry-run
    cd backend && python3.12 scripts/seed_efpia_stakeholder_map.py --apply    # write DB
"""

from __future__ import annotations

import pathlib

# Repo root derived from this file's location, so a repo move cannot break the script.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])


import argparse
import json
import logging
import sys
import uuid

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

TITLE = "Stakeholder map: EU health decision-makers (Brubru-curated)"

CONTENT = """# Stakeholder map: EU health decision-makers

_Curated by Brubru from its EU officials register (/api/v1/officials), 27 May 2026. Every named person below is a live record in Brubru: ask the chat about any of them by name, or open the profile via /api/v1/officials/{slug}._

## 1. European Commission

| Who | Role | Brubru slug |
|---|---|---|
| Oliver Varhelyi | Commissioner for Health and Animal Welfare (2024-2029) | `oliver-varhelyi-european-commission` |

The Commissioner's cabinet and the DG SANTE senior management are the day-to-day interlocutors on the pharmaceutical legislation revision, HTA and the Critical Medicines Act. Ask Brubru chat for DG SANTE leadership and current portfolio holders.

## 2. Council of the EU, Health configuration (EPSCO Health)

This is the forum where pricing, reimbursement, clawbacks and patient access are coordinated, and it maps directly onto EFPIA's national associations: each minister below is the counterpart for a member association (Farmaindustria for Spain, Leem for France, vfa for Germany, Farmindustria for Italy, and so on). Brubru holds all 27 Member State health ministers; the highest-value contacts:

| Member State | Minister | Brubru slug |
|---|---|---|
| Cyprus (Council Presidency, first half 2026) | Neofytos Charalambides | `neofytos-charalambides-council-of-the-eu` |
| Germany | Nina Warken | `nina-warken-council-of-the-eu` |
| France | Yannick Neuder | `yannick-neuder-council-of-the-eu` |
| Spain | Monica Garcia Gomez | `monica-garcia-gomez-council-of-the-eu` |
| Italy | Orazio Schillaci | `orazio-schillaci-council-of-the-eu` |
| Netherlands | Jan Anthonie Bruijn | `employmentmr-jan-anthonie-bruijn-council-of-the-eu` |
| Ireland | Jennifer Carroll MacNeill | `jennifer-carroll-macneill-council-of-the-eu` |
| Portugal | Ana Paula Martins | `ana-paula-martins-council-of-the-eu` |
| Denmark | Sophie Lohde | `sophie-lhde-council-of-the-eu` |
| Poland | Izabela Leszczyna | `izabela-leszczyna-council-of-the-eu` |
| Sweden | Elisabet Lann | `elisabet-lann-council-of-the-eu` |
| Finland | Kaisa Juuso | `kaisa-juuso-council-of-the-eu` |

All remaining Member State health ministers and several state secretaries are in Brubru: ask the chat, for example, "Who is the health minister of Belgium?" or "List the EU health ministers and their countries."

## 3. European Parliament

The pharmaceutical files run mainly through the Committee on the Environment, Public Health and Food Safety and its public-health subcommittee. The Critical Medicines Act is steered by rapporteur Tomislav Sokol of the EPP. Brubru tracks the committee secretariat contacts and links every legislative file to its rapporteur and shadows; ask the chat "Who is the rapporteur on the Critical Medicines Act?" or "Which committee handles the pharmaceutical legislation revision?".

## 4. Agencies

The European Medicines Agency is the scientific gatekeeper. Its committees (CHMP, PRAC, COMP) are now in your My EU Calendar with the full 2026 meeting schedule. Ask the chat about the EMA Executive Director and the role of each scientific committee.

## 5. How to use this map

- In chat: "Tell me about [name] and their position on the pharma reform."
- For your data team: the same records are available programmatically at `/api/v1/officials` (list) and `/api/v1/officials/{slug}` (profile).
- Coverage note: the Council Health configuration is comprehensive in Brubru; the Commission and Parliament entries are being expanded. Flag any missing contact and it can be added.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    apply = args.apply

    logger.info("=" * 78)
    logger.info(f"Add stakeholder map to {DEMO_EMAIL} - {'APPLY' if apply else 'DRY RUN'}")
    logger.info("=" * 78)

    db = SessionLocal()
    try:
        user_id = db.execute(text("SELECT id::text FROM users WHERE email=:e"), {"e": DEMO_EMAIL}).scalar()
        if not user_id:
            raise RuntimeError(f"Demo user {DEMO_EMAIL} not found.")

        exists = db.execute(
            text("SELECT 1 FROM user_documents WHERE user_id=:u AND title=:t"),
            {"u": user_id, "t": TITLE},
        ).first()
        if exists:
            logger.info("  [doc] SKIP stakeholder map (already present)")
        else:
            meta = {
                "original_document_type": "stakeholder_map",
                "generated_by": "brubru_officials_curation",
                "generated_at": "2026-05-27",
                "source_endpoints": ["/api/v1/officials", "/api/v1/officials/{slug}"],
            }
            if apply:
                db.execute(
                    text(
                        """
                        INSERT INTO user_documents (
                            id, user_id, document_type, title, content,
                            policy_areas, tags, executive_summary,
                            doc_metadata, include_in_ai_context, is_private,
                            version, view_count, is_featured, created_at, updated_at
                        ) VALUES (
                            :id, :u, 'uploaded', :title, :content,
                            :areas, :tags, :exec_sum,
                            CAST(:meta AS jsonb), true, true,
                            1, 0, true, NOW(), NOW()
                        )
                        """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "u": user_id,
                        "title": TITLE,
                        "content": CONTENT,
                        "areas": ["Public Health", "Pharmaceutical Legislation", "Access to Medicines"],
                        "tags": ["efpia", "stakeholder-map", "officials", "brubru-curated"],
                        "exec_sum": (
                            "Curated map of EU health decision-makers: the Health Commissioner, the "
                            "Council Health configuration (one minister per Member State, mapped to EFPIA "
                            "national associations), the Parliament health committees and the EMA. Every "
                            "official is a live Brubru record, queryable in chat and via /api/v1/officials."
                        ),
                        "meta": json.dumps(meta),
                    },
                )
                logger.info("  [doc] CREATE stakeholder map")
            else:
                logger.info("  [doc] WOULD CREATE stakeholder map")

        if apply:
            from scripts._validate_user_documents import validate_user_documents_for
            n = validate_user_documents_for(db, user_id)
            logger.info(f"  [validate] {n} user_documents rows round-trip cleanly")
            db.commit()
            logger.info("\n[OK] committed.")
        else:
            db.rollback()
            logger.info("\n[OK] dry-run only.")
    except Exception as e:
        db.rollback()
        logger.exception(f"FAILED: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
