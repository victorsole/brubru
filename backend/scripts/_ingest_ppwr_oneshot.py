"""One-shot ingestion of Reg (EU) 2025/40 (PPWR) into eu_laws and link it as
primary_law of the 'PPWR - Packaging and Packaging Waste Regulation' cluster.

Pattern lifted from _ingest_ehds_oneshot.py. Run AFTER
`create_law_clusters.py --package ppwr_packaging_and_packaging_waste` so the cluster row
exists for the primary_law link.

WARNING: the Formex parser can misread the title/CELEX for multi-file laws. After
running, verify the resulting eu_laws row and patch celex / title / date /
oj_reference / doc_type / policy_area manually if needed.
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
from backend.models.eu_law import EULaw, LawCluster
from backend.services.parsers.formex_parser import FormexParser
from backend.scripts.import_leg_archive import import_document

uuid = "d34251c8-d865-11ef-be2a-01aa75ed71a1"
xml_path = project_root / "docs/LEG_2025-11" / uuid / "fmx4/L_202500040EN.000101.fmx.xml"

CELEX = "32025R0040"
TITLE = (
    "Regulation (EU) 2025/40 of the European Parliament and of the Council of "
    "19 December 2024 on packaging and packaging waste, amending Regulation "
    "(EU) 2019/1020 and Directive (EU) 2019/904, and repealing Directive 94/62/EC"
)

print(f"xml exists: {xml_path.exists()} | size: {xml_path.stat().st_size if xml_path.exists() else 'n/a'}")
if not xml_path.exists():
    print("ABORT: source XML not found")
    sys.exit(1)

db = SessionLocal()
try:
    law = db.query(EULaw).filter(EULaw.celex == CELEX).first()
    if law:
        print(f"already ingested: id={law.id} celex={law.celex} — verifying metadata")
    else:
        parser = FormexParser()
        law = import_document(db, uuid, xml_path, parser, dry_run=False)
        if law and law.id is None:
            db.add(law); db.flush()
        if law:
            db.commit()
            print(f"imported PPWR: id={law.id} celex={law.celex} title={(law.title or '')[:160]}")

    if not law:
        print("import returned None — see logs above")
        sys.exit(1)

    needs_patch = (
        law.celex != CELEX
        or "packaging and packaging waste" not in (law.title or "").lower()
    )
    if needs_patch:
        print("[WARN] Formex parser misread the law — patching canonical metadata")
    law.celex = CELEX
    law.title = TITLE
    law.date = date(2024, 12, 19)
    law.oj_reference = "OJ L, 2025/40, 22.1.2025"
    law.doc_type = "Regulation"
    law.doc_type_normalized = "Regulation (EU)"
    law.policy_area = "Environment"
    law.celex_year = 2025
    law.celex_type = "R"
    law.celex_number = 40
    law.is_primary_legislation = True
    db.commit()
    print(f"patched eu_laws row id={law.id} celex={law.celex} date={law.date} policy={law.policy_area}")

    c = db.query(LawCluster).filter(
        LawCluster.name == "PPWR - Packaging and Packaging Waste Regulation"
    ).first()
    if c and not c.primary_law_id:
        c.primary_law_id = law.id
        db.commit()
        print(f"linked PPWR as primary_law_id of cluster {c.id}")
    elif c:
        print(f"cluster {c.id} already had primary_law_id={c.primary_law_id} — not overwriting")
    else:
        print("[WARN] cluster not found — run create_law_clusters.py --package ppwr_packaging_and_packaging_waste first")
finally:
    db.close()
