"""
Add three EFPIA data documents to David's MEUB Documents:

  1. The Pharmaceutical Industry in Figures 2025 (PIF 2025)  - the canonical
     annual EFPIA data dossier that backs the Data Center page.
  2. EFPIA W.A.I.T. Indicator 2025 - access-inequality evidence base.
  3. Frontier Economics Feb 2026 - economic impact of industry clinical trials.

Source PDFs were captured via WebFetch and parsed via pypdf; the extracted
text files are gitignored under data/apify/.

Pattern: document_type='uploaded' with semantic type in
doc_metadata.original_document_type (per memory/feedback_raw_insert_orm_defaults.md).
Validates via validate_user_documents_for() before commit.

Usage:
    cd backend && python3.12 scripts/seed_ddevant_efpia_data_dossier.py            # dry-run
    cd backend && python3.12 scripts/seed_ddevant_efpia_data_dossier.py --apply    # write DB
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys
import uuid

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


USER_EMAIL = "david.devantcerezo@efpia.eu"

DATA_DIR = pathlib.Path("/Users/victorsole/Documents/GitHub/brubru/data/apify")

# Cap PDF body at 100k chars (matches the FerrMed seed pattern + chat-context bounds).
MAX_BODY_CHARS = 100_000


DOCS = [
    {
        "title": "EFPIA Pharmaceutical Industry in Figures 2025 - full data tables",
        "original_document_type": "industry_dossier",
        "source_file": "efpia_pif_2025_text.txt",
        "source_url": "https://www.efpia.eu/media/uj0popel/the-pharmaceutical-industry-in-figures-2025.pdf",
        "policy_areas": ["Pharmaceutical Legislation", "Trade and IP"],
        "tags": ["efpia", "pif-2025", "industry-data", "data-center"],
        "executive_summary": (
            "EFPIA's canonical annual data dossier (Key Data 2025). Headline 2024 figures: "
            "EUR 55,000 million R&D investment in Europe; 950,000 direct employees including "
            "130,000 in R&D; production value EUR 440,000 million; trade balance EUR 220,000 "
            "million (with Switzerland and USA as top trading partners). Europe Top 5 share of "
            "world pharmaceutical market 15.8 percent vs USA 66.9 percent and Pharmerging 10.7 "
            "percent. This is the underlying dataset for the EFPIA Data Center 10 topics."
        ),
    },
    {
        "title": "EFPIA W.A.I.T. Indicator 2025 - patient access inequalities across Member States",
        "original_document_type": "evidence_base",
        "source_file": "efpia_wait_2025_text.txt",
        "source_url": "https://www.efpia.eu/media/mnfdwzax/efpia-patients-wait-indicator-2025.pdf",
        "policy_areas": ["Access to Medicines", "Pharmaceutical Legislation"],
        "tags": ["efpia", "wait-2025", "access", "patient-outcomes"],
        "executive_summary": (
            "EFPIA's annual evidence base on patient access to innovative medicines across "
            "European Member States. Measures time from EMA centralised approval to patient "
            "availability + share of new medicines accessible in each country. The headline "
            "narrative: deep gap between northern and western Europe (fast access) versus "
            "southern and eastern Europe (slow access). Anchor evidence for any EFPIA Europe's "
            "Choice ask on pricing acceleration and clawback elimination."
        ),
    },
    {
        "title": "Economic Impact of Industry Clinical Trials Across Europe - Frontier Economics, Feb 2026",
        "original_document_type": "commissioned_study",
        "source_file": "efpia_frontier_clinical_2026_text.txt",
        "source_url": "https://efpia.eu/media/zdzg0bey/the-economic-impact-of-industry-clinical-trials-across-europe.pdf",
        "policy_areas": ["Pharmaceutical Legislation", "Trade and IP"],
        "tags": ["frontier-economics", "clinical-trials", "gva", "spillovers"],
        "executive_summary": (
            "Independent Frontier Economics report for EFPIA (Feb 2026). Quantifies industry "
            "clinical-trials contribution to the European economy: ~EUR 35.7 billion in Gross "
            "Value Added per year, plus R&D spillover and workforce-productivity benefits. "
            "Forward-looking scenarios on the upside from increased clinical-trials volume. "
            "Carried out November 2025 - January 2026."
        ),
    },
]


def build_content(spec: dict) -> str:
    src = DATA_DIR / spec["source_file"]
    if not src.exists():
        return f"[Source file {spec['source_file']} missing. Re-run the EFPIA PDF extraction.]"
    raw = src.read_text(encoding="utf-8", errors="replace")
    body = raw[:MAX_BODY_CHARS]
    header = (
        f"# {spec['title']}\n\n"
        f"**Source PDF:** {spec['source_url']}\n"
        f"**Captured:** 21 May 2026 via WebFetch + pypdf extraction.\n"
        f"**Original document length:** {len(raw):,} characters\n"
    )
    if len(raw) > MAX_BODY_CHARS:
        header += f"**Note:** Body truncated to first {MAX_BODY_CHARS:,} chars for chat-context bounds.\n\n"
    else:
        header += "\n"
    return header + "---\n\n" + body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    apply = args.apply

    logger.info("=" * 78)
    logger.info(f"Add EFPIA data dossier to David Devant - {'APPLY' if apply else 'DRY RUN'}")
    logger.info("=" * 78)

    db = SessionLocal()
    try:
        user_id = db.execute(text("SELECT id::text FROM users WHERE email = :e"), {"e": USER_EMAIL}).scalar()
        if not user_id:
            raise RuntimeError(f"User {USER_EMAIL} not found")
        logger.info(f"  [user] {USER_EMAIL} (id={user_id[:8]})")

        for spec in DOCS:
            exists = db.execute(
                text("SELECT 1 FROM user_documents WHERE user_id = :u AND title = :t"),
                {"u": user_id, "t": spec["title"]},
            ).first()
            if exists:
                logger.info(f"  [doc] SKIP '{spec['title'][:60]}'")
                continue
            content = build_content(spec)
            meta = {
                "original_document_type": spec["original_document_type"],
                "source_url": spec["source_url"],
                "captured_at": "2026-05-21",
            }
            if apply:
                db.execute(
                    text("""
                        INSERT INTO user_documents (
                            id, user_id, document_type, title, content,
                            policy_areas, tags, executive_summary,
                            doc_metadata,
                            include_in_ai_context, is_private,
                            version, view_count, is_featured,
                            created_at, updated_at
                        ) VALUES (
                            :id, :u, 'uploaded', :title, :content,
                            :areas, :tags, :exec_sum,
                            CAST(:meta AS jsonb),
                            true, true,
                            1, 0, false,
                            NOW(), NOW()
                        )
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "u": user_id,
                        "title": spec["title"],
                        "content": content,
                        "areas": spec["policy_areas"],
                        "tags": spec["tags"],
                        "exec_sum": spec["executive_summary"],
                        "meta": json.dumps(meta),
                    },
                )
                logger.info(f"  [doc] CREATE [{spec['original_document_type']:<18}] '{spec['title'][:60]}' ({len(content):,} chars)")
            else:
                logger.info(f"  [doc] WOULD CREATE [{spec['original_document_type']:<18}] '{spec['title'][:60]}' ({len(content):,} chars)")

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
