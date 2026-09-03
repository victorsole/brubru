"""
Fix two issues with the EFPIA demo account (public-affairs@efpia.eu) Documents:

  1. Editability: everything was seeded as document_type='uploaded', which the
     Documents tab treats as read-only (openEdit blocks 'uploaded'). The authored
     briefings / position papers / talking points / stakeholder map should be
     editable. Remap their document_type to an editable type based on
     doc_metadata.original_document_type. The three genuine source-PDF dossiers
     (W.A.I.T., Pharma in Figures, Frontier Economics) stay 'uploaded'.

  2. Slugs leaking to the user: the stakeholder-map body exposed internal
     officials slugs (e.g. oliver-varhelyi-european-commission) and /api/v1/...
     paths. Rewrite it cleanly (names, roles, countries; no slugs, no API paths).

Usage:
    cd backend && python3.12 scripts/fix_efpia_demo_documents.py            # dry-run
    cd backend && python3.12 scripts/fix_efpia_demo_documents.py --apply
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

# original_document_type (in doc_metadata) -> editable document_type.
# Genuine source PDFs stay 'uploaded' (large, not authored, not inline-editable).
KEEP_UPLOADED = {"evidence_base", "commissioned_study", "industry_dossier"}
TYPE_MAP = {
    "position_paper": "strategy",
    "analysis": "analysis",
    "briefing_note": "analysis",
    "mep_briefing": "note",
    "talking_points": "note",
    "policy_summary": "note",
    "stakeholder_map": "note",
}

STAKEHOLDER_TITLE = "Stakeholder map: EU health decision-makers (Brubru-curated)"
STAKEHOLDER_CONTENT = """# Stakeholder map: EU health decision-makers

A curated map of the people who shape EU health and pharmaceutical policy. Ask Brubru chat about any of them for their role, brief and current positions.

## 1. European Commission
- **Oliver Varhelyi** — Commissioner for Health and Animal Welfare (2024-2029). His cabinet and the DG SANTE senior management are the day-to-day interlocutors on the pharmaceutical legislation revision, HTA and the Critical Medicines Act.

## 2. Council of the EU, Health configuration (EPSCO Health)
This is where pricing, reimbursement, clawbacks and patient access are coordinated, and it maps directly onto EFPIA's national associations: each minister is the counterpart for a member association (Farmaindustria for Spain, Leem for France, vfa for Germany, Farmindustria for Italy, and so on). The highest-value contacts:

- **Cyprus** (Council Presidency, first half 2026) — Neofytos Charalambides
- **Germany** — Nina Warken
- **France** — Yannick Neuder
- **Spain** — Monica Garcia Gomez
- **Italy** — Orazio Schillaci
- **Netherlands** — Jan Anthonie Bruijn
- **Ireland** — Jennifer Carroll MacNeill
- **Portugal** — Ana Paula Martins
- **Denmark** — Sophie Lohde
- **Poland** — Izabela Leszczyna
- **Sweden** — Elisabet Lann
- **Finland** — Kaisa Juuso

All 27 Member State health ministers are tracked in Brubru. Ask the chat, for example, "Who is the health minister of Belgium?" or "List the EU health ministers and their countries."

## 3. European Parliament
The pharmaceutical files run mainly through the Committee on the Environment, Public Health and Food Safety and its public-health subcommittee. The Critical Medicines Act is steered by rapporteur Tomislav Sokol (EPP). Ask Brubru "Who is the rapporteur on the Critical Medicines Act?" or "Which committee handles the pharmaceutical legislation revision?".

## 4. European Medicines Agency
The EMA is the scientific gatekeeper. Its committees (CHMP, PRAC, COMP) are in your My EU Calendar with the full 2026 meeting schedule. Ask the chat about the EMA Executive Director and the role of each scientific committee.

## How to use this map
Ask Brubru in chat, for example: "Tell me about Nina Warken and her position on the pharma reform", or "Which health ministers face re-election this year?".
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    apply = args.apply

    db = SessionLocal()
    try:
        uid = db.execute(text("SELECT id::text FROM users WHERE email=:e"), {"e": DEMO_EMAIL}).scalar()
        if not uid:
            raise RuntimeError(f"Demo user {DEMO_EMAIL} not found")

        rows = db.execute(
            text("SELECT id::text, title, document_type, doc_metadata->>'original_document_type' AS odt "
                 "FROM user_documents WHERE user_id=:u"),
            {"u": uid},
        ).all()

        logger.info(f"  {len(rows)} documents for {DEMO_EMAIL}")
        for r in rows:
            odt = r.odt or ""
            if odt in KEEP_UPLOADED:
                logger.info(f"  [keep uploaded] {r.title[:55]}  (orig={odt})")
                continue
            new_type = TYPE_MAP.get(odt, "note")
            if r.document_type == new_type:
                logger.info(f"  [already {new_type}] {r.title[:55]}")
            else:
                logger.info(f"  [{r.document_type} -> {new_type}] {r.title[:55]}")
                if apply:
                    db.execute(
                        text("UPDATE user_documents SET document_type=:t, updated_at=NOW() WHERE id=:i"),
                        {"t": new_type, "i": r.id},
                    )

        # Rewrite stakeholder map content (strip slugs + API paths)
        sm = db.execute(
            text("SELECT id::text FROM user_documents WHERE user_id=:u AND title=:t"),
            {"u": uid, "t": STAKEHOLDER_TITLE},
        ).scalar()
        if sm:
            logger.info("  [stakeholder map] rewriting content (remove slugs + /api/v1 paths)")
            if apply:
                db.execute(
                    text("UPDATE user_documents SET content=:c, updated_at=NOW() WHERE id=:i"),
                    {"c": STAKEHOLDER_CONTENT, "i": sm},
                )
        else:
            logger.warning("  [stakeholder map] not found by title")

        if apply:
            from scripts._validate_user_documents import validate_user_documents_for
            n = validate_user_documents_for(db, uid)
            logger.info(f"  [validate] {n} rows round-trip cleanly")
            db.commit()
            logger.info("\n[OK] committed.")
        else:
            db.rollback()
            logger.info("\n[OK] dry-run. Re-run with --apply.")
    except Exception as e:
        db.rollback()
        logger.exception(f"FAILED: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
