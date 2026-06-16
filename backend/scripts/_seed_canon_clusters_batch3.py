"""Seed the DSA and DMA canon laws into EU Law Comply (cluster + requirements).
Same idempotent pattern as _seed_canon_clusters_batch2.py.
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

PA = "Digital Policy and Platform Regulation"
LAWS = {
    "32022R2065": dict(
        title="Regulation (EU) 2022/2065 of the European Parliament and of the Council of 19 October 2022 on a Single Market For Digital Services (Digital Services Act)",
        doc_date=date(2022, 10, 19), slug="2022-2065_dsa",
        cluster="Digital Services Act (Regulation (EU) 2022/2065)",
        desc="The EU horizontal rulebook for intermediary services: the conditional liability exemptions and ban on general monitoring, the tiered due-diligence duties (all intermediaries, hosting, online platforms, and the extra obligations on Very Large Online Platforms and Search Engines), notice-and-action, statements of reasons, trusted flaggers, the ban on dark patterns, advertising transparency and protection of minors, recommender-system transparency, systemic-risk assessment and audits, researcher data access, and enforcement by Digital Services Coordinators and the Commission with fines up to 6 percent of worldwide turnover.",
        applicability="Providers of intermediary services offered to users in the EU: mere conduit, caching and hosting services, online platforms, and the designated VLOPs and VLOSEs."),
    "32022R1925": dict(
        title="Regulation (EU) 2022/1925 of the European Parliament and of the Council of 14 September 2022 on contestable and fair markets in the digital sector (Digital Markets Act)",
        doc_date=date(2022, 9, 14), slug="2022-1925_dma",
        cluster="Digital Markets Act (Regulation (EU) 2022/1925)",
        desc="The EU ex-ante rules for gatekeepers of core platform services: the designation thresholds and market-investigation route, the Article 5, 6 and 7 do's and don'ts (no cross-service data combination without consent, no self-preferencing, no anti-steering, interoperability, data portability and real-time access for business users, FRAND app-store access, messaging interoperability), the anti-circumvention duty, the compliance function, and enforcement by the Commission alone with fines up to 10 percent of worldwide turnover rising to 20 percent for repeat infringements plus structural remedies.",
        applicability="Undertakings designated as gatekeepers providing core platform services, and the business users and end users that rely on them."),
}


def upsert(db, celex, meta):
    law = db.query(EULaw).filter(EULaw.celex == celex).first()
    url = f"https://brubru.beresol.eu/eucanon/{meta['slug']}/"
    if law:
        law.is_primary_legislation = True
        em = dict(law.extra_metadata or {}); em["eucanon_url"] = url
        law.extra_metadata = em; db.flush(); return law, False
    nid = db.execute(text("""
        INSERT INTO eu_laws (uuid, celex, title, doc_type, date, policy_area,
            is_primary_legislation, celex_year, celex_type, celex_number,
            doc_type_normalized, xml_path, extra_metadata)
        VALUES (:uuid,:celex,:title,'regulation',:d,:pa,true,:yr,:ty,:num,'regulation',:xp,CAST(:em AS json))
        RETURNING id"""), {
        "uuid": str(uuid.uuid4()), "celex": celex, "title": meta["title"], "d": meta["doc_date"],
        "pa": PA, "yr": int(celex[1:5]), "ty": celex[5], "num": int(celex[6:]), "xp": f"canon:{celex}",
        "em": json.dumps({"eucanon_url": url, "source": "canon_marquee_2026"})}).scalar()
    db.flush(); return db.query(EULaw).filter(EULaw.id == nid).first(), True


def main():
    db = SessionLocal(); summ = []
    try:
        for celex, meta in LAWS.items():
            law, created = upsert(db, celex, meta)
            cl = db.query(LawCluster).filter(LawCluster.name == meta["cluster"]).first()
            if not cl:
                cl = LawCluster(name=meta["cluster"]); db.add(cl)
            cl.primary_law_id = law.id; cl.description = meta["desc"]; cl.applicability = meta["applicability"]
            cl.policy_area = PA[:100]; cl.priority_level = "high"; db.flush()
            db.query(ClusterLaw).filter(ClusterLaw.cluster_id == cl.id).delete()
            db.add(ClusterLaw(cluster_id=cl.id, law_id=law.id, relationship_type="primary"))
            db.query(LawRequirement).filter(LawRequirement.cluster_id == cl.id).delete()
            reqs = json.loads(Path(f"/tmp/req_{celex}.json").read_text())
            for r in reqs:
                db.add(LawRequirement(law_id=law.id, cluster_id=cl.id, article=r["article"][:50],
                    requirement_text=r["requirement_text"], criticality=r["criticality"][:20],
                    applicable_entity=r["applicable_entity"][:100]))
            summ.append((celex, "new" if created else "exists", law.id, cl.id, len(reqs)))
        db.commit()
        for s in summ:
            print(f"{s[0]} {s[1]} law_id={s[2]} cluster_id={s[3]} reqs={s[4]}")
    except Exception:
        db.rollback(); import traceback; traceback.print_exc(); raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
