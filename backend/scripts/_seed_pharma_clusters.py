"""Seed the 10 EFPIA pharma-canon laws into EU Law Comply: upsert the eu_laws rows
that are missing, create one clean primary-only law_cluster per law, link the law as
primary in cluster_laws, and seed law_requirements from the hand-extracted headline
obligations in /tmp/req_<celex>.json (grounded in data/canon/<slug>.analysis.md).

Idempotent: re-running replaces the cluster's requirements + primary link in place.
No LLM, no Anthropic API. Brubru EFPIA pharma canon, June 2026.

law_requirements.article is VARCHAR(50), applicable_entity VARCHAR(100), criticality VARCHAR(20).
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

POLICY_AREA = "Public Health and Pharmaceuticals"

# celex -> metadata. doc_date is the act's signature date.
LAWS = {
    "32004R0726": dict(
        title="Regulation (EC) No 726/2004 laying down Union procedures for the authorisation and supervision of medicinal products for human and veterinary use and establishing a European Medicines Agency",
        doc_type="regulation", doc_date=date(2004, 3, 31),
        cluster="EMA and Centralised Authorisation (Regulation 726/2004)",
        desc="The regulation that created the European Medicines Agency and the centralised marketing-authorisation procedure for medicinal products in the EU.",
        applicability="Marketing authorisation holders and applicants using the centralised procedure, the EMA, biotech and innovative-medicine developers.",
        slug="2004-726_ema"),
    "32000R0141": dict(
        title="Regulation (EC) No 141/2000 of the European Parliament and of the Council on orphan medicinal products",
        doc_type="regulation", doc_date=date(1999, 12, 16),
        cluster="Orphan Medicines (Regulation 141/2000)",
        desc="The EU incentive framework for medicines treating rare conditions: orphan designation, protocol assistance, fee reductions and ten-year market exclusivity.",
        applicability="Sponsors developing medicines for rare diseases, the EMA Committee for Orphan Medicinal Products (COMP).",
        slug="2000-141_orphan"),
    "32014R0536": dict(
        title="Regulation (EU) No 536/2014 of the European Parliament and of the Council on clinical trials on medicinal products for human use",
        doc_type="regulation", doc_date=date(2014, 4, 16),
        cluster="Clinical Trials Regulation (Regulation 536/2014)",
        desc="The single EU framework for authorising and supervising clinical trials through the Clinical Trials Information System (CTIS), with a coordinated assessment procedure.",
        applicability="Clinical-trial sponsors, investigators, Member State authorities and ethics committees, CROs.",
        slug="2014-536_ctr"),
    "32007R1394": dict(
        title="Regulation (EC) No 1394/2007 of the European Parliament and of the Council on advanced therapy medicinal products",
        doc_type="regulation", doc_date=date(2007, 11, 13),
        cluster="Advanced Therapy Medicinal Products (Regulation 1394/2007)",
        desc="The lex specialis for gene therapy, somatic cell therapy and tissue-engineered products, with the Committee for Advanced Therapies (CAT) and the hospital exemption.",
        applicability="Developers and manufacturers of ATMPs, the EMA Committee for Advanced Therapies, hospitals using the exemption.",
        slug="2007-1394_atmp"),
    "32006R1901": dict(
        title="Regulation (EC) No 1901/2006 of the European Parliament and of the Council on medicinal products for paediatric use",
        doc_type="regulation", doc_date=date(2006, 12, 12),
        cluster="Paediatric Medicines (Regulation 1901/2006)",
        desc="The framework requiring paediatric investigation plans (PIPs), with rewards and incentives to ensure medicines are studied for use in children.",
        applicability="Marketing authorisation holders and applicants, the EMA Paediatric Committee (PDCO).",
        slug="2006-1901_paediatric"),
    "32001L0083": dict(
        title="Directive 2001/83/EC of the European Parliament and of the Council on the Community code relating to medicinal products for human use",
        doc_type="directive", doc_date=date(2001, 11, 6),
        cluster="Community Code on Medicinal Products (Directive 2001/83/EC)",
        desc="The consolidated Community code governing national, mutual-recognition and decentralised authorisation, manufacturing, labelling, classification, distribution, advertising and pharmacovigilance of human medicines.",
        applicability="All human-medicine marketing authorisation holders, manufacturers, wholesalers and national competent authorities.",
        slug="2001-83_community_code"),
    "32004L0024": dict(
        title="Directive 2004/24/EC of the European Parliament and of the Council amending, as regards traditional herbal medicinal products, Directive 2001/83/EC",
        doc_type="directive", doc_date=date(2004, 3, 31),
        cluster="Traditional Herbal Medicines (Directive 2004/24/EC)",
        desc="The simplified traditional-use registration scheme for herbal medicinal products, with the EMA Committee on Herbal Medicinal Products (HMPC).",
        applicability="Manufacturers and registrants of traditional herbal medicinal products, national authorities, the HMPC.",
        slug="2004-24_herbal"),
    "32010L0084": dict(
        title="Directive 2010/84/EU of the European Parliament and of the Council amending, as regards pharmacovigilance, Directive 2001/83/EC",
        doc_type="directive", doc_date=date(2010, 12, 15),
        cluster="Pharmacovigilance (Directive 2010/84/EU)",
        desc="The 2010 pharmacovigilance overhaul: the PRAC, EudraVigilance single reporting, risk-management plans, the black triangle and the urgent Union procedure.",
        applicability="Marketing authorisation holders, national competent authorities, the EMA Pharmacovigilance Risk Assessment Committee (PRAC).",
        slug="2010-84_pharmacovigilance"),
    "32011L0062": dict(
        title="Directive 2011/62/EU of the European Parliament and of the Council amending Directive 2001/83/EC as regards the prevention of the entry into the legal supply chain of falsified medicinal products",
        doc_type="directive", doc_date=date(2011, 6, 8),
        cluster="Falsified Medicines (Directive 2011/62/EU)",
        desc="The safety-features regime (unique identifier and anti-tampering device verified through the EMVS), plus active-substance and broker controls, against falsified medicines.",
        applicability="Manufacturers, wholesale distributors, brokers, pharmacies, active-substance suppliers, the EMVO/EMVS.",
        slug="2011-62_falsified_medicines"),
    "32012L0026": dict(
        title="Directive 2012/26/EU of the European Parliament and of the Council amending Directive 2001/83/EC as regards pharmacovigilance",
        doc_type="directive", doc_date=date(2012, 10, 25),
        cluster="Pharmacovigilance Amendments (Directive 2012/26/EU)",
        desc="The post-Mediator follow-up that made the urgent Union procedure trigger automatically and forced disclosure of safety-driven withdrawals, including in third countries.",
        applicability="Marketing authorisation holders, national competent authorities, the PRAC.",
        slug="2012-26_pv_amend"),
}


def upsert_law(db, celex, meta):
    law = db.query(EULaw).filter(EULaw.celex == celex).first()
    eucanon_url = f"https://brubru.beresol.eu/eucanon/{meta['slug']}/"
    if law:
        # ensure it is treated as primary legislation and carries the deep-dive link
        law.is_primary_legislation = True
        em = dict(law.extra_metadata or {})
        em["eucanon_url"] = eucanon_url
        law.extra_metadata = em
        db.flush()
        return law, False
    # Raw INSERT to avoid the ORM trying to write the generated search_vector column.
    new_id = db.execute(text("""
        INSERT INTO eu_laws (uuid, celex, title, doc_type, date, policy_area,
            is_primary_legislation, celex_year, celex_type, celex_number,
            doc_type_normalized, xml_path, extra_metadata)
        VALUES (:uuid, :celex, :title, :doc_type, :date, :policy_area,
            true, :yr, :ty, :num, :dtn, :xmlp, CAST(:em AS json))
        RETURNING id
    """), {
        "uuid": str(uuid.uuid4()), "celex": celex, "title": meta["title"],
        "doc_type": meta["doc_type"], "date": meta["doc_date"], "policy_area": POLICY_AREA,
        "yr": int(celex[1:5]), "ty": celex[5], "num": int(celex[6:]),
        "dtn": meta["doc_type"], "xmlp": f"efpia_canon:{celex}",
        "em": json.dumps({"eucanon_url": eucanon_url, "source": "efpia_pharma_canon_2026"}),
    }).scalar()
    db.flush()
    law = db.query(EULaw).filter(EULaw.id == new_id).first()
    return law, True


def get_or_create_cluster(db, meta, law_id):
    cl = db.query(LawCluster).filter(LawCluster.name == meta["cluster"]).first()
    if not cl:
        cl = LawCluster(name=meta["cluster"])
        db.add(cl)
    cl.primary_law_id = law_id
    cl.description = meta["desc"]
    cl.applicability = meta["applicability"]
    cl.policy_area = POLICY_AREA[:100]
    cl.priority_level = "high"
    db.flush()
    return cl


def main():
    db = SessionLocal()
    created_laws = 0
    summary = []
    try:
        for celex, meta in LAWS.items():
            law, was_created = upsert_law(db, celex, meta)
            created_laws += int(was_created)
            cl = get_or_create_cluster(db, meta, law.id)

            # clean primary link: remove existing rows for this cluster, add one primary
            db.query(ClusterLaw).filter(ClusterLaw.cluster_id == cl.id).delete()
            db.add(ClusterLaw(cluster_id=cl.id, law_id=law.id, relationship_type="primary"))

            # reseed requirements for this law+cluster
            db.query(LawRequirement).filter(
                LawRequirement.cluster_id == cl.id
            ).delete()
            reqs = json.loads(Path(f"/tmp/req_{celex}.json").read_text())
            for r in reqs:
                db.add(LawRequirement(
                    law_id=law.id,
                    cluster_id=cl.id,
                    article=r["article"][:50],
                    requirement_text=r["requirement_text"],
                    criticality=r["criticality"][:20],
                    applicable_entity=r["applicable_entity"][:100],
                ))
            summary.append((celex, "new" if was_created else "exists", law.id, cl.id, len(reqs)))
        db.commit()
        print(f"[OK] committed. New eu_laws rows: {created_laws}")
        print(f"{'CELEX':12} {'law':6} {'law_id':>7} {'cluster_id':>10} {'reqs':>5}")
        for celex, st, lid, cid, n in summary:
            print(f"{celex:12} {st:6} {lid:>7} {cid:>10} {n:>5}")
        print(f"TOTAL requirements seeded: {sum(s[4] for s in summary)}")
    except Exception:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
