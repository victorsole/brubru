"""One-shot ingestion of Reg (EU) 2023/956 (CBAM) into eu_laws and link it as
primary_law of the 'CBAM Package (Carbon Border Adjustment Mechanism)' cluster.

Pattern lifted from _ingest_china_bev_oneshot.py. Run AFTER
`create_law_clusters.py --package cbam` so the cluster row exists for the primary_law link.

WARNING: the Formex parser can misread the title/CELEX for multi-file laws (CBAM annexes
live in sibling XML files). After running, verify the resulting eu_laws row and patch
celex / title / date / oj_reference / doc_type / policy_area manually if needed.
"""
import sys
from datetime import date
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw, LawCluster
from backend.services.parsers.formex_parser import FormexParser
from backend.scripts.import_leg_archive import import_document

uuid = "e5587bf5-f383-11ed-a05c-01aa75ed71a1"
xml_path = project_root / "docs/LEG_2025-11" / uuid / "fmx4/L_2023130EN.01005201.xml"

CELEX = "32023R0956"
TITLE = (
    "Regulation (EU) 2023/956 of the European Parliament and of the Council of "
    "10 May 2023 establishing a carbon border adjustment mechanism"
)

print(f"xml exists: {xml_path.exists()} | size: {xml_path.stat().st_size if xml_path.exists() else 'n/a'}")
if not xml_path.exists():
    print("ABORT: source XML not found")
    sys.exit(1)

db = SessionLocal()
try:
    # If already present (re-run safety), reuse the existing row
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
            print(f"imported CBAM: id={law.id} celex={law.celex} title={(law.title or '')[:160]}")

    if not law:
        print("import returned None — see logs above")
        sys.exit(1)

    # Patch canonical metadata if the parser misread the multi-file act
    needs_patch = (
        law.celex != CELEX
        or "carbon border adjustment" not in (law.title or "").lower()
    )
    if needs_patch:
        print("[WARN] Formex parser misread the law — patching canonical metadata")
    law.celex = CELEX
    law.title = TITLE
    law.date = date(2023, 5, 10)
    law.oj_reference = "OJ L 130/52, 16.5.2023"
    law.doc_type = "Regulation"
    law.doc_type_normalized = "Regulation (EU)"
    law.policy_area = "Climate Action"
    law.celex_year = 2023
    law.celex_type = "R"
    law.celex_number = 956
    law.is_primary_legislation = True
    db.commit()
    print(f"patched eu_laws row id={law.id} celex={law.celex} date={law.date} policy={law.policy_area}")

    c = db.query(LawCluster).filter(
        LawCluster.name == "CBAM Package (Carbon Border Adjustment Mechanism)"
    ).first()
    if c and not c.primary_law_id:
        c.primary_law_id = law.id
        db.commit()
        print(f"linked CBAM as primary_law_id of cluster {c.id}")
    elif c:
        print(f"cluster {c.id} already had primary_law_id={c.primary_law_id} — not overwriting")
    else:
        print("[WARN] cluster not found — run create_law_clusters.py --package cbam first")
finally:
    db.close()
