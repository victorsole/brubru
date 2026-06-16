"""Seed the NIS2 Directive canon law into EU Law Comply. One-law variant of
_seed_canon_clusters_batch2.py."""
import json, sys, uuid
from datetime import date
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root)); sys.path.insert(0, str(project_root / "backend"))
from dotenv import load_dotenv
load_dotenv(project_root / ".env")
from sqlalchemy import text
from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw, LawCluster, ClusterLaw, LawRequirement

CELEX="32022L2555"; SLUG="2022-2555_nis2"
CLUSTER="NIS2 Directive (Directive (EU) 2022/2555)"
PA="Cybersecurity and Digital Infrastructure"
TITLE=("Directive (EU) 2022/2555 of the European Parliament and of the Council of 14 December 2022 on "
       "measures for a high common level of cybersecurity across the Union (NIS2 Directive)")
DESC=("The EU baseline cybersecurity regime, replacing NIS1: it brings essential and important entities "
      "across 18 sectors into scope, makes management bodies accountable, mandates ten minimum risk-management "
      "measures including supply-chain security (Article 21), sets a three-stage incident-reporting cascade "
      "(early warning within 24 hours, notification within 72 hours, final report within one month, Article 23), "
      "and provides for differentiated supervision and fines up to EUR 10 million or 2 percent of worldwide "
      "turnover for essential entities and EUR 7 million or 1.4 percent for important entities.")
APPLIC=("Public and private essential and important entities in the Annex I and II sectors above the size cap "
        "(generally medium and large), plus specified entities regardless of size, that provide services in the EU.")

def main():
    db=SessionLocal()
    try:
        law=db.query(EULaw).filter(EULaw.celex==CELEX).first()
        url=f"https://brubru.beresol.eu/eucanon/{SLUG}/"
        if law:
            law.is_primary_legislation=True
            em=dict(law.extra_metadata or {}); em["eucanon_url"]=url; law.extra_metadata=em; db.flush(); created=False
        else:
            nid=db.execute(text("""INSERT INTO eu_laws (uuid,celex,title,doc_type,date,policy_area,
                is_primary_legislation,celex_year,celex_type,celex_number,doc_type_normalized,xml_path,extra_metadata)
                VALUES (:uuid,:celex,:title,'directive',:d,:pa,true,2022,'L',2555,'directive',:xp,CAST(:em AS json))
                RETURNING id"""),{"uuid":str(uuid.uuid4()),"celex":CELEX,"title":TITLE,"d":date(2022,12,14),
                "pa":PA,"xp":f"canon:{CELEX}","em":json.dumps({"eucanon_url":url,"source":"canon_marquee_2026"})}).scalar()
            db.flush(); law=db.query(EULaw).filter(EULaw.id==nid).first(); created=True
        cl=db.query(LawCluster).filter(LawCluster.name==CLUSTER).first()
        if not cl: cl=LawCluster(name=CLUSTER); db.add(cl)
        cl.primary_law_id=law.id; cl.description=DESC; cl.applicability=APPLIC; cl.policy_area=PA[:100]; cl.priority_level="high"; db.flush()
        db.query(ClusterLaw).filter(ClusterLaw.cluster_id==cl.id).delete()
        db.add(ClusterLaw(cluster_id=cl.id,law_id=law.id,relationship_type="primary"))
        db.query(LawRequirement).filter(LawRequirement.cluster_id==cl.id).delete()
        reqs=json.loads(Path(f"/tmp/req_{CELEX}.json").read_text())
        for r in reqs:
            db.add(LawRequirement(law_id=law.id,cluster_id=cl.id,article=r["article"][:50],
                requirement_text=r["requirement_text"],criticality=r["criticality"][:20],applicable_entity=r["applicable_entity"][:100]))
        db.commit()
        print(f"NIS2 seeded: law_id={law.id} ({'new' if created else 'exists'}) cluster_id={cl.id} reqs={len(reqs)}")
    except Exception:
        db.rollback(); import traceback; traceback.print_exc(); raise
    finally:
        db.close()

if __name__=="__main__": main()
