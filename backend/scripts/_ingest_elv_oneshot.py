"""One-shot ingest of the End-of-Life Vehicles Regulation into eu_laws.

Why this exists
---------------
Regulation (EU) 2026/1738 entered into force on 13 August 2026 and Brubru could
not cite it: `eu_laws` had the 2000 ELV Directive and its amending directives,
but nothing for the Regulation that repeals them. `eu_laws` still has no
recurring ingest, so every act published after the November 2025 bulk export
arrives through a one-shot like this one.

Source
------
Every fact below is read from the act's own text, fetched from EUR-Lex through
the project's WAF browser fetcher on the day it entered into force, not from a
summary or a press release:

  https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R1738
  ELI: http://publications.europa.eu/resource/eli/reg/2026/1738/oj

Verified from that text: Article 59 (entry into force on the twentieth day
after publication; application from 1 September 2028; Article 53 from
13 August 2026; Article 55 from 1 September 2032), Article 2 (category
phase-in), Article 6 (15% recycled plastic from 2032, 25% from 2036, at least
20% of it from end-of-life vehicles), Article 13 (Digital Circularity Vehicle
Passport from 1 September 2032), Article 57 (repeal of Directive 2000/53/EC
from 1 September 2028, with Annex II entries 5(a), 5(b)(i), 5(b)(ii) and 16
ceasing on 13 August 2026), and Annex XII (the replacement table for Annex I of
the Batteries Regulation).

Why a raw INSERT and not the ORM
--------------------------------
`eu_laws.search_vector` is GENERATED ALWAYS in Postgres but declared writable on
the model, so any ORM insert raises. The fix is an explicit column list that
omits it. `xml_path` is NOT NULL and this act has no Formex file in the corpus,
so it carries the `cellar://` convention already used by the DPP one-shots.

Usage:
  python3.12 -m scripts._ingest_elv_oneshot --dry-run
  python3.12 -m scripts._ingest_elv_oneshot --apply
"""
import argparse
import json
import sys
import uuid as _uuid
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

import logging  # noqa: E402

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

CELEX = "32026R1738"
TITLE = (
    "Regulation (EU) 2026/1738 of the European Parliament and of the Council of "
    "8 July 2026 on circularity requirements for vehicle design and on management "
    "of end-of-life vehicles, amending Regulations (EU) No 168/2013, (EU) 2018/858, "
    "(EU) 2019/1020 and (EU) 2023/1542 and repealing Directives 2000/53/EC and "
    "2005/64/EC (Text with EEA relevance)"
)
DATE = "2026-07-08"
OJ_REFERENCE = "OJ L, 2026/1738, 24.7.2026"
DOC_TYPE = "Regulation"
POLICY_AREA = "Environment, Climate and Circular Economy"
CORPUS_VERSION = "OJ_2026-08"
XML_PATH = f"cellar://publications.europa.eu/resource/celex/{CELEX}"
ELI = "http://publications.europa.eu/resource/eli/reg/2026/1738/oj"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    db = SessionLocal()
    plan = []
    try:
        law_id = db.execute(text("SELECT id FROM eu_laws WHERE celex=:x"),
                            {"x": CELEX}).scalar()
        if law_id:
            plan.append(f"eu_laws row already present (id {law_id})")
        else:
            law_id = db.execute(text("""
                INSERT INTO eu_laws
                    (uuid, celex, doc_type, doc_type_normalized, title, date,
                     oj_reference, policy_area, xml_path, is_primary_legislation,
                     corpus_version, corpus_status, celex_year, celex_type,
                     celex_number, extra_metadata)
                VALUES
                    (:uuid, :celex, :doc_type, :doc_type, :title, :date,
                     :oj, :area, :xml, true,
                     :cv, 'active', 2026, 'R', 1738, CAST(:meta AS jsonb))
                RETURNING id"""),
                {"uuid": str(_uuid.uuid4()), "celex": CELEX, "doc_type": DOC_TYPE,
                 "title": TITLE, "date": DATE, "oj": OJ_REFERENCE,
                 "area": POLICY_AREA, "xml": XML_PATH, "cv": CORPUS_VERSION,
                 "meta": json.dumps({
                     "short_name": "End-of-Life Vehicles Regulation",
                     "eli": ELI,
                     "articles": 59,
                     "entry_into_force": "2026-08-13",
                     "applies_from": "2028-09-01",
                     "early_application": {"2026-08-13": "Article 53",
                                           "2026-09-14": "delegated empowerments"},
                     "repeals": ["32000L0053", "32005L0064"],
                     "amends": ["32013R0168", "32018R0858", "32019R1020",
                                "32023R1542"],
                     "ingested_by": "_ingest_elv_oneshot"})}).scalar()
            plan.append(f"INSERT eu_laws {CELEX} -> id {law_id}")

        print("=== PLAN ===")
        for p in plan:
            print("  -", p)

        if not apply:
            db.rollback()
            print("\n[DRY-RUN] nothing written. Re-run with --apply")
            return 0

        db.commit()
        row = db.execute(text(
            "SELECT id, celex, date, corpus_version, left(title,60) "
            "FROM eu_laws WHERE celex=:x"), {"x": CELEX}).fetchone()
        print(f"\n[OK] committed: {tuple(row)}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
