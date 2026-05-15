"""One-shot ingestion of CRR (32013R0575) into eu_laws + link as primary_law of CRR cluster."""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from dotenv import load_dotenv
load_dotenv(project_root / ".env")
from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw, LawCluster
from backend.services.parsers.formex_parser import FormexParser
from backend.scripts.import_leg_archive import import_document

xml_path = project_root / "docs/LEG_2025-11/ccd31733-df06-11e2-9165-01aa75ed71a1/fmx4/L_2013176EN.01000101.xml"
uuid = "ccd31733-df06-11e2-9165-01aa75ed71a1"
print(f"xml exists: {xml_path.exists()} | size: {xml_path.stat().st_size if xml_path.exists() else 'n/a'}")
db = SessionLocal()
try:
    parser = FormexParser()
    law = import_document(db, uuid, xml_path, parser, dry_run=False)
    if law and law.id is None:
        db.add(law); db.flush()
    if law:
        db.commit()
        print(f"imported CRR: id={law.id} celex={law.celex} title={(law.title or '')[:120]}")
        c = db.query(LawCluster).filter(LawCluster.name == "CRR / CRD IV - Bank Prudential Requirements").first()
        if c and not c.primary_law_id:
            c.primary_law_id = law.id
            db.commit()
            print(f"linked CRR as primary_law_id of cluster {c.id}")
        elif c:
            print(f"cluster {c.id} already had primary_law_id={c.primary_law_id}")
    else:
        print("import returned None — see logs above")
finally:
    db.close()
