"""One-shot ingest of the Digital Omnibus on AI, Regulation (EU) 2026/1744, into eu_laws.

Why this exists
---------------
Found 15 September 2026: `GET /api/v2/legislative/eur-lex/laws/32026R1744`
returned 404. `eu_laws` has no recurring ingest. Its rows come from the
November 2025 Publications Office bulk export (`LEG_2025-11`, newest act dated
5 November 2025) plus hand one-shots like `_ingest_elv_oneshot` and
`_ingest_payments_oneshot`. `sync_eurlex_via_sparql.py` (run by the daily cron)
discovers new OJ acts from Cellar but writes them to `legislative_carriages`,
never to `eu_laws`. So no window, sector filter or OJ-numbering rule excluded
this act: nothing published after the bulk export reaches `eu_laws` unless a
one-shot puts it there.

Source
------
Every fact below was read from the Cellar metadata graph for the work
`cellar:b459c07f-86fb-11f1-bf5e-01aa75ed71a1` on 15 September 2026
(`resource_legal_*` and `official-journal-act_*` predicates), not from press:

  title, signature/document date 2026-07-08, OJ L publication 2026-07-24
  (act number 2026/1744), entry into force 2026-07-27, in force, EEA relevance,
  based on Article 114 TFEU (12016E114), amends 32024R1689, 32018R1139 and
  32023R1230, adopts proposal 52025PC0836, responsible DG CNECT,
  consolidations 02024R1689-20260727, 02018R1139-20260802, 02023R1230-20260727.

Why a raw INSERT and not the ORM: see `_ingest_elv_oneshot` (search_vector is
GENERATED ALWAYS; xml_path NOT NULL, so the `cellar://` convention).

Idempotent: an existing row for the CELEX is left untouched.

Usage:
  python3.12 -m scripts._ingest_ai_omnibus_oneshot --dry-run
  python3.12 -m scripts._ingest_ai_omnibus_oneshot --apply
"""
import argparse
import json
import logging
import sys
import uuid as _uuid
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

CELEX = "32026R1744"
DOC_TYPE = "Regulation"
TITLE = (
    "Regulation (EU) 2026/1744 of the European Parliament and of the Council of "
    "8 July 2026 amending Regulations (EU) 2024/1689, (EU) 2018/1139 and (EU) "
    "2023/1230 as regards the simplification of the implementation of harmonised "
    "rules on artificial intelligence (Digital Omnibus on AI) (Text with EEA relevance)"
)
DATE = "2026-07-08"
OJ_REFERENCE = "OJ L, 2026/1744, 24.7.2026"
POLICY_AREA = "Digital / AI"  # same value as the AI Act row it amends
LEGAL_BASIS = ["Article 114 TFEU"]
CORPUS_VERSION = "OJ_2026-09"
XML_PATH = f"cellar://publications.europa.eu/resource/celex/{CELEX}"
META = {
    "short_name": "Digital Omnibus on AI",
    "eli": "http://data.europa.eu/eli/reg/2026/1744/oj",
    "oj_publication_date": "2026-07-24",
    "entry_into_force": "2026-07-27",
    "eea_relevance": True,
    "amends": ["32024R1689", "32018R1139", "32023R1230"],
    "based_on": ["12016E114"],
    "proposal": "52025PC0836",
    "responsible_dg": "CNECT",
    "consolidated_versions_created": [
        "02024R1689-20260727", "02018R1139-20260802", "02023R1230-20260727",
    ],
    "ingested_by": "_ingest_ai_omnibus_oneshot",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    db = SessionLocal()
    plan = []
    try:
        existing = db.execute(
            text("SELECT id FROM eu_laws WHERE celex=:x"), {"x": CELEX}
        ).scalar()
        if existing:
            plan.append(f"{CELEX} already present (id {existing}) - skipped")
        else:
            new_id = db.execute(
                text(
                    """
                    INSERT INTO eu_laws
                        (uuid, celex, doc_type, doc_type_normalized, title, date,
                         oj_reference, policy_area, legal_basis, xml_path,
                         is_primary_legislation, corpus_version, corpus_status,
                         celex_year, celex_type, celex_number, extra_metadata)
                    VALUES
                        (:uuid, :celex, :doc_type, :doc_type, :title, :date,
                         :oj, :area, :basis, :xml,
                         true, :cv, 'active',
                         2026, 'R', 1744, CAST(:meta AS jsonb))
                    RETURNING id"""
                ),
                {
                    "uuid": str(_uuid.uuid4()), "celex": CELEX, "doc_type": DOC_TYPE,
                    "title": TITLE, "date": DATE, "oj": OJ_REFERENCE,
                    "area": POLICY_AREA, "basis": LEGAL_BASIS, "xml": XML_PATH,
                    "cv": CORPUS_VERSION, "meta": json.dumps(META),
                },
            ).scalar()
            plan.append(f"INSERT {CELEX} (Digital Omnibus on AI) -> id {new_id}")

        print("=== PLAN ===")
        for p in plan:
            print("  -", p)

        if not apply:
            db.rollback()
            print("\n[DRY-RUN] nothing written. Re-run with --apply")
            return 0

        db.commit()
        row = db.execute(
            text("SELECT id, celex, date, oj_reference, policy_area, legal_basis "
                 "FROM eu_laws WHERE celex=:x"),
            {"x": CELEX},
        ).first()
        if not row:
            print("[ERROR] row not found after commit")
            return 1
        print(f"\n[OK] committed; verified: {tuple(row)}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
