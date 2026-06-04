"""One-shot ingestion of Reg (EU) 2024/2754 (China BEV countervailing duties) into eu_laws
and link it as primary_law of the 'China BEV Countervailing Duties (Reg 2024/2754)' cluster.

Pattern lifted from _ingest_crr_oneshot.py. Run AFTER `create_law_clusters.py --package china_bev_countervailing_duties`
so the cluster row exists for the primary_law_id link.

WARNING: the Formex parser may misread the title/CELEX for large Implementing Regulations.
After running, verify the resulting eu_laws row and patch celex / title / date_adopted /
oj_reference / document_type / policy_area manually if needed (see canon.md gotchas).
"""
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

# Resolve from the CSV register so we never hard-code the wrong UUID
xml_path = project_root / "docs/LEG_2025-11/0109a10f-9621-11ef-a130-01aa75ed71a1/fmx4/L_202402754EN.000101.fmx.xml"
uuid = "0109a10f-9621-11ef-a130-01aa75ed71a1"

print(f"xml exists: {xml_path.exists()} | size: {xml_path.stat().st_size if xml_path.exists() else 'n/a'}")
if not xml_path.exists():
    print("ABORT: source XML not found")
    sys.exit(1)

db = SessionLocal()
try:
    parser = FormexParser()
    law = import_document(db, uuid, xml_path, parser, dry_run=False)
    if law and law.id is None:
        db.add(law); db.flush()
    if law:
        db.commit()
        print(f"imported BEV CVD: id={law.id} celex={law.celex} title={(law.title or '')[:160]}")

        # If Formex misread, patch the canonical metadata
        needs_patch = (
            law.celex != "32024R2754"
            or (law.title or "").lower().find("countervailing") < 0
        )
        if needs_patch:
            print("[WARN] Formex parser misread the law — patching canonical metadata")
            law.celex = "32024R2754"
            law.title = (
                "Commission Implementing Regulation (EU) 2024/2754 of 29 October 2024 "
                "imposing a definitive countervailing duty on imports of new battery electric "
                "vehicles designed for the transport of persons originating in the "
                "People's Republic of China"
            )
            # Patch other fields conservatively only if the parser left them empty/wrong
            from datetime import date
            if not law.date_adopted:
                law.date_adopted = date(2024, 10, 29)
            if not law.oj_reference:
                law.oj_reference = "OJ L, 2024/2754, 30.10.2024"
            if not law.document_type:
                law.document_type = "Regulation"  # Implementing Regulation maps to Regulation
            if not law.policy_area:
                law.policy_area = "Trade"
            db.commit()
            print(f"patched eu_laws row id={law.id}")

        c = db.query(LawCluster).filter(LawCluster.name == "China BEV Countervailing Duties (Reg 2024/2754)").first()
        if c and not c.primary_law_id:
            c.primary_law_id = law.id
            db.commit()
            print(f"linked BEV CVD as primary_law_id of cluster {c.id}")
        elif c:
            print(f"cluster {c.id} already had primary_law_id={c.primary_law_id} — not overwriting")
        else:
            print("[WARN] cluster not found — run create_law_clusters.py first")
    else:
        print("import returned None — see logs above")
finally:
    db.close()
