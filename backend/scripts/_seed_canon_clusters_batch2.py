"""Seed the 6 niche State-aid decision canon laws into EU Law Comply:
upsert the eu_laws row if missing, create one clean primary-only law_cluster per
decision, link the law as primary, and seed law_requirements from
/tmp/req_<celex>.json (extracted from each decision's analysis).

State-aid Commission Decisions are NOT transposed, so there is no transposition
map. The cluster simply holds the compliance principles the decision establishes.

Idempotent. No LLM, no Anthropic API. Same pattern as _seed_canon_clusters_batch1.py.
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

PA = "Competition and State Aid"
LAWS = {
    "32018D0859": dict(
        title="Commission Decision (EU) 2018/859 of 4 October 2017 on State aid SA.38944 implemented by Luxembourg to Amazon",
        doc_date=date(2017, 10, 4), slug="2018-859_amazon_state_aid",
        cluster="Amazon State Aid Decision (Decision (EU) 2018/859)",
        desc="The Commission found that a Luxembourg tax ruling let Amazon shift most of its EU profit to a non-taxed partnership via an intra-group royalty that departed from the arm's-length principle, conferring a selective advantage and unlawful State aid. The General Court annulled the decision in 2021 and the Court of Justice dismissed the Commission's appeal in 2023.",
        applicability="Multinational groups using intra-group licensing and transfer pricing; tax authorities issuing advance rulings."),
    "32017D1283": dict(
        title="Commission Decision (EU) 2017/1283 of 30 August 2016 on State aid SA.38373 implemented by Ireland to Apple",
        doc_date=date(2016, 8, 30), slug="2017-1283_apple_state_aid",
        cluster="Apple State Aid Decision (Decision (EU) 2017/1283)",
        desc="The Commission found that two Irish tax rulings allocated almost all of Apple's sales profits to stateless head offices with no real activity, leaving the Irish branches under-taxed, a selective advantage and unlawful State aid of up to about EUR 13 billion. The General Court annulled the decision in 2020 but the Court of Justice set that aside in 2024 and confirmed the Commission, so Ireland must recover the aid.",
        applicability="Multinational groups allocating profit to branches; tax authorities issuing advance rulings."),
    "32023D1683": dict(
        title="Commission Decision (EU) 2023/1683 of 26 July 2022 on measure SA.26494 implemented by France for La Rochelle airport and certain airlines",
        doc_date=date(2022, 7, 26), slug="2023-1683_la_rochelle_airport",
        cluster="La Rochelle Airport State Aid Decision (Decision (EU) 2023/1683)",
        desc="The Commission assessed public funding to the operator of La Rochelle airport and the airport-services and marketing agreements concluded with airlines including Ryanair. Applying the market-economy operator principle with an incremental-profitability analysis, it found unlawful aid to the airlines and ordered recovery, while assessing the airport operating aid under the Aviation Guidelines.",
        applicability="Regional airport operators and public authorities; airlines signing marketing and airport-services agreements."),
    "32016D0633": dict(
        title="Commission Decision (EU) 2016/633 of 23 July 2014 on State aid SA.33961 implemented by France for Nimes airport, Ryanair and Airport Marketing Services",
        doc_date=date(2014, 7, 23), slug="2016-633_nimes_airport",
        cluster="Nimes Airport State Aid Decision (Decision (EU) 2016/633)",
        desc="The Commission examined public funding to the managers of Nimes airport and the airport-services and marketing agreements with Ryanair and Airport Marketing Services. Using the market-economy operator test and an incremental-profitability analysis, it found unlawful aid in several agreements and ordered recovery, assessing airport operating aid under the Aviation Guidelines.",
        applicability="Regional airport operators and chambers of commerce; airlines signing marketing and airport-services agreements."),
    "32025D1963": dict(
        title="Commission Decision (EU) 2025/1963 of 21 November 2024 on measure SA.39639 implemented by Italy for the Cineca consortium",
        doc_date=date(2024, 11, 21), slug="2025-1963_cineca",
        cluster="Cineca State Aid Decision (Decision (EU) 2025/1963)",
        desc="The Commission examined the Italian inter-university consortium Cineca and the in-house assignment of public IT and supercomputing services. It assessed whether Cineca is an undertaking carrying on economic activity and whether any selective advantage from public resources distorted competition, clarifying when in-house public-service arrangements stay outside the State-aid rules.",
        applicability="Public bodies and in-house entities providing services to their public members; Member States structuring in-house assignments."),
    "32020D1412": dict(
        title="Commission Decision (EU) 2020/1412 of 2 March 2020 on measures SA.32014, SA.32015, SA.32016 implemented by Italy for Tirrenia di Navigazione and Compagnia Italiana di Navigazione",
        doc_date=date(2020, 3, 2), slug="2020-1412_tirrenia",
        cluster="Tirrenia State Aid Decision (Decision (EU) 2020/1412)",
        desc="The Commission assessed public-service compensation for maritime cabotage routes, priority berthing and tax measures granted to Tirrenia, and whether recovery follows to its acquirer Compagnia Italiana di Navigazione through economic continuity. It applied the Altmark conditions and the SGEI framework under Article 106(2) TFEU and found some measures incompatible aid.",
        applicability="Public-service operators receiving SGEI compensation; Member States entrusting maritime cabotage; purchasers of businesses subject to recovery."),
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
        "doc_type": "decision", "date": meta["doc_date"], "policy_area": PA,
        "yr": int(celex[1:5]), "ty": celex[5], "num": int(celex[6:]),
        "dtn": "decision", "xmlp": f"canon:{celex}",
        "em": json.dumps({"eucanon_url": eucanon_url, "source": "canon_state_aid_decisions_2026"}),
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
            cl.policy_area = PA[:100]
            cl.priority_level = "medium"
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
