"""Seed the GDPR canon law into EU Law Comply (cluster + requirements).
Same idempotent pattern as _seed_canon_clusters_batch2.py, for one regulation.
"""
import json
import sys
import uuid
from datetime import date
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from sqlalchemy import text
from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw, LawCluster, ClusterLaw, LawRequirement

CELEX = "32016R0679"
SLUG = "2016-679_gdpr"
CLUSTER = "GDPR (Regulation (EU) 2016/679)"
PA = "Data Protection and Privacy"
TITLE = ("Regulation (EU) 2016/679 of the European Parliament and of the Council of 27 April 2016 "
         "on the protection of natural persons with regard to the processing of personal data and "
         "on the free movement of such data (General Data Protection Regulation)")
DESC = ("The EU general data protection regime: the principles of processing, the six lawful bases, "
        "consent, special categories, data-subject rights (access, rectification, erasure, portability, "
        "objection, automated decisions), controller and processor duties (data protection by design, "
        "records, DPIA, the DPO, security, 72-hour breach notification), international transfers "
        "(adequacy, SCCs, BCRs), the one-stop-shop and the EDPB, and administrative fines up to "
        "EUR 20 million or 4 percent of total worldwide annual turnover.")
APPLIC = ("Any controller or processor handling personal data of people in the EU, including "
          "organisations established outside the EU that target or monitor EU data subjects (Article 3).")


def main():
    db = SessionLocal()
    try:
        law = db.query(EULaw).filter(EULaw.celex == CELEX).first()
        eucanon_url = f"https://brubru.beresol.eu/eucanon/{SLUG}/"
        if law:
            law.is_primary_legislation = True
            em = dict(law.extra_metadata or {}); em["eucanon_url"] = eucanon_url
            law.extra_metadata = em; db.flush(); created = False
        else:
            new_id = db.execute(text("""
                INSERT INTO eu_laws (uuid, celex, title, doc_type, date, policy_area,
                    is_primary_legislation, celex_year, celex_type, celex_number,
                    doc_type_normalized, xml_path, extra_metadata)
                VALUES (:uuid,:celex,:title,'regulation',:d,:pa,true,:yr,:ty,:num,'regulation',:xp,CAST(:em AS json))
                RETURNING id"""), {
                "uuid": str(uuid.uuid4()), "celex": CELEX, "title": TITLE, "d": date(2016, 4, 27),
                "pa": PA, "yr": 2016, "ty": "R", "num": 679, "xp": f"canon:{CELEX}",
                "em": json.dumps({"eucanon_url": eucanon_url, "source": "canon_marquee_2026"})}).scalar()
            db.flush(); law = db.query(EULaw).filter(EULaw.id == new_id).first(); created = True

        cl = db.query(LawCluster).filter(LawCluster.name == CLUSTER).first()
        if not cl:
            cl = LawCluster(name=CLUSTER); db.add(cl)
        cl.primary_law_id = law.id; cl.description = DESC; cl.applicability = APPLIC
        cl.policy_area = PA[:100]; cl.priority_level = "high"; db.flush()

        db.query(ClusterLaw).filter(ClusterLaw.cluster_id == cl.id).delete()
        db.add(ClusterLaw(cluster_id=cl.id, law_id=law.id, relationship_type="primary"))
        db.query(LawRequirement).filter(LawRequirement.cluster_id == cl.id).delete()
        reqs = json.loads(Path(f"/tmp/req_{CELEX}.json").read_text())
        for r in reqs:
            db.add(LawRequirement(law_id=law.id, cluster_id=cl.id, article=r["article"][:50],
                requirement_text=r["requirement_text"], criticality=r["criticality"][:20],
                applicable_entity=r["applicable_entity"][:100]))
        db.commit()
        print(f"GDPR seeded: law_id={law.id} ({'new' if created else 'exists'}) cluster_id={cl.id} reqs={len(reqs)}")
    except Exception:
        db.rollback(); import traceback; traceback.print_exc(); raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
