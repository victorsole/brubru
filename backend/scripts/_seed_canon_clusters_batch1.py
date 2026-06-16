"""Seed the 3 framework-directive canon laws (EECC, Solvency II, MiFID II) into
EU Law Comply: upsert the eu_laws row if missing, create one clean primary-only
law_cluster per law, link the law as primary, and seed law_requirements from
/tmp/req_<celex>.json (extracted from data/canon/<slug>.analysis.md).

Idempotent. No LLM, no Anthropic API. Reuses the pattern of _seed_pharma_clusters.py.
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

LAWS = {
    "32018L1972": dict(
        title="Directive (EU) 2018/1972 of the European Parliament and of the Council establishing the European Electronic Communications Code (Recast)",
        doc_type="directive", doc_date=date(2018, 12, 11),
        policy_area="Digital Policy and Telecommunications",
        cluster="European Electronic Communications Code (Directive 2018/1972)",
        desc="The recast single code for electronic communications networks and services: market regulation and SMP remedies, very-high-capacity network deployment, radio spectrum, general authorisation, end-user rights and universal service, and BEREC governance.",
        applicability="Providers of electronic communications networks and services, national regulatory authorities, BEREC, spectrum users.",
        slug="2018-1972_eecc"),
    "32009L0138": dict(
        title="Directive 2009/138/EC of the European Parliament and of the Council on the taking-up and pursuit of the business of Insurance and Reinsurance (Solvency II)",
        doc_type="directive", doc_date=date(2009, 11, 25),
        policy_area="Financial Services and Insurance",
        cluster="Solvency II (Directive 2009/138/EC)",
        desc="The EU risk-based prudential regime for insurers and reinsurers: the Solvency Capital Requirement and Minimum Capital Requirement, market-consistent technical provisions, own-funds tiering, the prudent-person principle, the system of governance and ORSA, public disclosure (SFCR) and group supervision.",
        applicability="Insurance and reinsurance undertakings, insurance groups, national supervisors and EIOPA.",
        slug="2009-138_solvency2"),
    "32014L0065": dict(
        title="Directive 2014/65/EU of the European Parliament and of the Council on markets in financial instruments (MiFID II)",
        doc_type="directive", doc_date=date(2014, 5, 15),
        policy_area="Financial Services and Markets",
        cluster="MiFID II (Directive 2014/65/EU)",
        desc="The recast markets-in-financial-instruments framework: authorisation and organisation of investment firms, the venue taxonomy (regulated market, MTF and the new OTF), algorithmic and high-frequency trading controls, investor protection (best execution, suitability, product governance, inducements), commodity position limits and data reporting services. Companion to MiFIR.",
        applicability="Investment firms, trading venues, data reporting service providers, national competent authorities and ESMA.",
        slug="2014-65_mifid2"),
}


def upsert_law(db, celex, meta):
    law = db.query(EULaw).filter(EULaw.celex == celex).first()
    eucanon_url = f"https://brubru.beresol.eu/eucanon/{meta['slug']}/"
    if law:
        law.is_primary_legislation = True
        em = dict(law.extra_metadata or {})
        em["eucanon_url"] = eucanon_url
        law.extra_metadata = em
        db.flush()
        return law, False
    new_id = db.execute(text("""
        INSERT INTO eu_laws (uuid, celex, title, doc_type, date, policy_area,
            is_primary_legislation, celex_year, celex_type, celex_number,
            doc_type_normalized, xml_path, extra_metadata)
        VALUES (:uuid, :celex, :title, :doc_type, :date, :policy_area,
            true, :yr, :ty, :num, :dtn, :xmlp, CAST(:em AS json))
        RETURNING id
    """), {
        "uuid": str(uuid.uuid4()), "celex": celex, "title": meta["title"],
        "doc_type": meta["doc_type"], "date": meta["doc_date"], "policy_area": meta["policy_area"],
        "yr": int(celex[1:5]), "ty": celex[5], "num": int(celex[6:]),
        "dtn": meta["doc_type"], "xmlp": f"canon:{celex}",
        "em": json.dumps({"eucanon_url": eucanon_url, "source": "canon_framework_directives_2026"}),
    }).scalar()
    db.flush()
    return db.query(EULaw).filter(EULaw.id == new_id).first(), True


def main():
    db = SessionLocal()
    summary = []
    try:
        for celex, meta in LAWS.items():
            law, was_created = upsert_law(db, celex, meta)
            cl = db.query(LawCluster).filter(LawCluster.name == meta["cluster"]).first()
            if not cl:
                cl = LawCluster(name=meta["cluster"])
                db.add(cl)
            cl.primary_law_id = law.id
            cl.description = meta["desc"]
            cl.applicability = meta["applicability"]
            cl.policy_area = meta["policy_area"][:100]
            cl.priority_level = "high"
            db.flush()

            db.query(ClusterLaw).filter(ClusterLaw.cluster_id == cl.id).delete()
            db.add(ClusterLaw(cluster_id=cl.id, law_id=law.id, relationship_type="primary"))

            db.query(LawRequirement).filter(LawRequirement.cluster_id == cl.id).delete()
            reqs = json.loads(Path(f"/tmp/req_{celex}.json").read_text())
            for r in reqs:
                db.add(LawRequirement(
                    law_id=law.id, cluster_id=cl.id,
                    article=r["article"][:50], requirement_text=r["requirement_text"],
                    criticality=r["criticality"][:20], applicable_entity=r["applicable_entity"][:100],
                ))
            summary.append((celex, "new" if was_created else "exists", law.id, cl.id, len(reqs)))
        db.commit()
        print(f"{'CELEX':12} {'law':6} {'law_id':>7} {'cluster_id':>10} {'reqs':>5}")
        for s in summary:
            print(f"{s[0]:12} {s[1]:6} {s[2]:>7} {s[3]:>10} {s[4]:>5}")
        print(f"TOTAL requirements seeded: {sum(s[4] for s in summary)}")
    except Exception:
        db.rollback(); import traceback; traceback.print_exc(); raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
