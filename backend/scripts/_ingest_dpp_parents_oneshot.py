"""One-shot ingestion of the two acts that define the Digital Product Passport but were
missing from eu_laws: the ESPR (32024R1781) and the Batteries Regulation (32023R1542).

Found 5 August 2026 during the Terraqui / LIFE DPP-TEX query audit. Of twelve flagship
acts checked against eu_laws, exactly these two were absent, and they are precisely the
DPP framework act and the first passport in force. Their CORRIGENDA were present
(32024R90493, 32025R90356 for the ESPR; 32024R90243, 32025R90794 for Batteries), so the
corpus import created child rows without their parent.

Consequence while missing: CELEX lookup, law search and ask_brubru's "relevant EU laws"
could not surface either act, so answers about the Digital Product Passport were built
from web search rather than from the corpus that already held the text.

Pattern lifted from _ingest_ppwr_oneshot.py. The Formex parser is known to misread
title/CELEX on multi-file laws, so this script patches the row explicitly afterwards
rather than trusting the parse.
"""
import sys
from datetime import date
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw
from backend.services.parsers.formex_parser import FormexParser
from backend.scripts.import_leg_archive import import_document

ACTS = [
    {
        "celex": "32024R1781",
        "uuid": "66b9f8da-34ea-11ef-b441-01aa75ed71a1",
        "rel": "fmx4/L_202401781EN.000101.fmx.xml",
        "title": (
            "Regulation (EU) 2024/1781 of the European Parliament and of the Council of "
            "13 June 2024 establishing a framework for the setting of ecodesign "
            "requirements for sustainable products, amending Directive (EU) 2020/1828 "
            "and Regulation (EU) 2023/1542 and repealing Directive 2009/125/EC"
        ),
        "date": date(2024, 6, 13),
        "oj_reference": "OJ L, 2024/1781, 28.6.2024",
        "policy_area": "Environment",
    },
    {
        "celex": "32023R1542",
        "uuid": "d0065c31-2ce3-11ee-95a2-01aa75ed71a1",
        "rel": "fmx4/L_2023191EN.01000101.xml",
        "title": (
            "Regulation (EU) 2023/1542 of the European Parliament and of the Council of "
            "12 July 2023 concerning batteries and waste batteries, amending Directive "
            "2008/98/EC and Regulation (EU) 2019/1020 and repealing Directive 2006/66/EC"
        ),
        "date": date(2023, 7, 12),
        "oj_reference": "OJ L 191, 28.7.2023, p. 1",
        "policy_area": "Environment",
    },
]


def main() -> int:
    db = SessionLocal()
    rc = 0
    try:
        for a in ACTS:
            xml = project_root / "docs/LEG_2025-11" / a["uuid"] / a["rel"]
            print(f"\n=== {a['celex']} ===")
            print(f"xml exists: {xml.exists()}"
                  f"{' size=' + str(xml.stat().st_size) if xml.exists() else ''}")
            if not xml.exists():
                print("  SKIP: source XML not found")
                rc = 1
                continue

            law = db.query(EULaw).filter(EULaw.celex == a["celex"]).first()
            if law:
                print(f"  already present: id={law.id}")
            else:
                parser = FormexParser()
                law = import_document(db, a["uuid"], xml, parser, dry_run=False)
                if law and law.id is None:
                    db.add(law)
                    db.flush()
                if not law:
                    print("  import returned None")
                    rc = 1
                    continue
                db.commit()
                print(f"  imported: id={law.id} parsed_celex={law.celex}")

            # Patch metadata explicitly: the parser misreads multi-file laws
            law.celex = a["celex"]
            law.title = a["title"]
            law.date = a["date"]
            law.oj_reference = a["oj_reference"]
            law.policy_area = a["policy_area"]
            law.doc_type = "Regulation"
            law.doc_type_normalized = "Regulation"
            law.celex_year = int(a["celex"][1:5])
            law.celex_type = a["celex"][5]
            law.celex_number = int(a["celex"][6:])
            law.is_primary_legislation = True
            db.commit()
            print(f"  patched -> celex={law.celex} date={law.date} "
                  f"type={law.doc_type} title={law.title[:70]}...")

        print("\n=== verification ===")
        for a in ACTS:
            n = db.query(EULaw).filter(EULaw.celex == a["celex"]).count()
            print(f"  {a['celex']}: {n} row(s) {'OK' if n == 1 else 'PROBLEM'}")
            if n != 1:
                rc = 1
    finally:
        db.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
