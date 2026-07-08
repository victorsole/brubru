"""One-shot ingestion of Reg (EU) 2025/327 (EHDS) into eu_laws and link it as
primary_law of the 'EHDS - European Health Data Space' cluster.

Pattern lifted from _ingest_cbam_oneshot.py. Run AFTER
`create_law_clusters.py --package ehds_european_health_data_space` so the cluster row
exists for the primary_law link.

WARNING: the Formex parser can misread the title/CELEX for multi-file laws (EHDS annexes
live in sibling XML files). After running, verify the resulting eu_laws row and patch
celex / title / date / oj_reference / doc_type / policy_area manually if needed.
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

uuid = "531b8c37-f962-11ef-b7db-01aa75ed71a1"
xml_path = project_root / "docs/LEG_2025-11" / uuid / "fmx4/L_202500327EN.000101.fmx.xml"

CELEX = "32025R0327"
TITLE = (
    "Regulation (EU) 2025/327 of the European Parliament and of the Council of "
    "11 February 2025 on the European Health Data Space and amending Directive "
    "2011/24/EU and Regulation (EU) 2024/2847"
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
            print(f"imported EHDS: id={law.id} celex={law.celex} title={(law.title or '')[:160]}")

    if not law:
        print("import returned None — see logs above")
        sys.exit(1)

    needs_patch = (
        law.celex != CELEX
        or "european health data space" not in (law.title or "").lower()
    )
    if needs_patch:
        print("[WARN] Formex parser misread the law — patching canonical metadata")
    law.celex = CELEX
    law.title = TITLE
    law.date = date(2025, 2, 11)
    law.oj_reference = "OJ L, 2025/327, 5.3.2025"
    law.doc_type = "Regulation"
    law.doc_type_normalized = "Regulation (EU)"
    law.policy_area = "Public Health"
    law.celex_year = 2025
    law.celex_type = "R"
    law.celex_number = 327
    law.is_primary_legislation = True
    db.commit()
    print(f"patched eu_laws row id={law.id} celex={law.celex} date={law.date} policy={law.policy_area}")

    c = db.query(LawCluster).filter(
        LawCluster.name == "EHDS - European Health Data Space"
    ).first()
    if c and not c.primary_law_id:
        c.primary_law_id = law.id
        db.commit()
        print(f"linked EHDS as primary_law_id of cluster {c.id}")
    elif c:
        print(f"cluster {c.id} already had primary_law_id={c.primary_law_id} — not overwriting")
    else:
        print("[WARN] cluster not found — run create_law_clusters.py --package ehds_european_health_data_space first")
finally:
    db.close()
