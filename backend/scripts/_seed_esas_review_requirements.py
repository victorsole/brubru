"""Seed the canonical headline obligations of Regulation (EU) 2019/2175 (the ESAs Review)
into law_requirements.

This is an omnibus amending regulation, so the obligations it creates land in the six target
regulations and fall mostly on the ESAs (EBA/EIOPA/ESMA) and national competent authorities,
with some on financial sector operators, data reporting services providers and benchmark
administrators. Pre-curated from a full read of the regulation + the analysis at
data/canon/2019-2175_esas_review.analysis.md (Brubru canon project, May 2026).

ids verified live against prod Supabase on 25 May 2026:
  SELECT id, celex FROM eu_laws WHERE celex='32019R2175';  -> 11327
  SELECT id, name FROM law_clusters WHERE name LIKE 'ESAs Review%';  -> 25
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from backend.core.database import SessionLocal
from backend.models.eu_law import LawRequirement

ESAS_LAW_ID = 11327
ESAS_CLUSTER_ID = 25

REQUIREMENTS = [
    {
        "article": "Article 1 / EBA Art 9a (AML leading role)",
        "requirement_text": (
            "EBA shall take a leading, coordinating and monitoring role in preventing and "
            "countering money laundering and terrorist financing across the entire financial "
            "sector (banking, insurance and securities), collecting AML weakness information "
            "from competent authorities, developing common AML guidance and technical "
            "standards, and assessing AML/CFT risks."
        ),
        "criticality": "critical",
        "applicable_entity": "EBA / national competent authorities",
    },
    {
        "article": "Article 1 / EBA Art 9a(2) (central AML database)",
        "requirement_text": (
            "EBA shall establish and keep up to date a central database of AML/CFT weakness "
            "information collected from competent authorities, analyse it, and make it "
            "available to competent authorities on a need-to-know and confidential basis. EBA "
            "had to develop the regulatory technical standards specifying the collection and "
            "the database by 31 December 2020."
        ),
        "criticality": "critical",
        "applicable_entity": "EBA",
    },
    {
        "article": "Article 1 / EBA Art 9a(7) (internal AML committee)",
        "requirement_text": (
            "EBA shall establish a permanent internal AML/CFT committee composed of high-level "
            "representatives of every Member State's AML authorities (one vote per Member "
            "State), with EIOPA and ESMA participating without a vote and the Commission, ESRB "
            "and ECB Supervisory Board as observers. It replaced the former Joint Committee "
            "AML subcommittee."
        ),
        "criticality": "important",
        "applicable_entity": "EBA / Member State AML authorities",
    },
    {
        "article": "Article 1 / EBA Art 9b (request for investigation)",
        "requirement_text": (
            "Where EBA has indications of material AML breaches, it may request a competent "
            "authority to investigate possible breaches and to consider sanctions or an "
            "individual decision against the financial sector operator. The competent "
            "authority must inform EBA of the steps taken within 10 working days; failing "
            "that, the breach-of-Union-law procedure (Article 17) applies."
        ),
        "criticality": "critical",
        "applicable_entity": "competent authority / financial operator",
    },
    {
        "article": "Article 1 / Art 9c (no-action letters)",
        "requirement_text": (
            "In exceptional circumstances (an act conflicting with another, missing delegated "
            "or implementing acts, or missing guidelines), the ESA shall notify competent "
            "authorities and the Commission in writing, provide an opinion on appropriate "
            "action, and make that opinion public."
        ),
        "criticality": "informational",
        "applicable_entity": "EBA / EIOPA / ESMA",
    },
    {
        "article": "Article 1 / Art 16b (questions and answers)",
        "requirement_text": (
            "Each ESA shall establish and maintain a web-based questions-and-answers tool open "
            "to any natural or legal person in any official EU language, publish admissible "
            "questions and answers (non-binding), and forward questions requiring "
            "interpretation of Union law to the Commission."
        ),
        "criticality": "informational",
        "applicable_entity": "EBA / EIOPA / ESMA",
    },
    {
        "article": "Art 17a (reporting persons protection)",
        "requirement_text": (
            "Each ESA shall operate dedicated whistleblower reporting channels allowing "
            "anonymous or confidential and safe submissions, protect reporting persons from "
            "retaliation in line with the Whistleblower Directive (EU) 2019/1937, and provide "
            "feedback where the information shows a material breach."
        ),
        "criticality": "important",
        "applicable_entity": "EBA / EIOPA / ESMA",
    },
    {
        "article": "Art 29a (strategic supervisory priorities)",
        "requirement_text": (
            "Each ESA shall, at least every three years by 31 March, identify up to two "
            "Union-wide supervisory priorities. Competent authorities shall take those "
            "priorities into account when drawing up their work programmes and notify the ESA "
            "accordingly."
        ),
        "criticality": "important",
        "applicable_entity": "ESAs / national competent authorities",
    },
    {
        "article": "Article 1 / Art 30 (peer reviews)",
        "requirement_text": (
            "Each ESA shall periodically conduct peer reviews of competent authorities through "
            "ad hoc peer review committees (Authority staff plus competent-authority members, "
            "chaired by Authority staff), assessing resources, independence, governance, "
            "convergence and enforcement. The report is adopted by the Board of Supervisors, a "
            "follow-up report follows after two years, and the main findings are published."
        ),
        "criticality": "important",
        "applicable_entity": "ESAs / national competent authorities",
    },
    {
        "article": "Article 1 / Art 31a (fitness and propriety)",
        "requirement_text": (
            "The three ESAs shall jointly establish a system for exchanging information "
            "relevant to the assessment of the fitness and propriety of qualifying-holding "
            "holders, directors and key function holders of financial institutions."
        ),
        "criticality": "informational",
        "applicable_entity": "ESAs / national competent authorities",
    },
    {
        "article": "Art 33 (third-country equivalence)",
        "requirement_text": (
            "Each ESA shall monitor the regulatory, supervisory and enforcement developments "
            "in third countries underpinning Commission equivalence decisions and submit a "
            "confidential annual report. It shall not conclude administrative arrangements "
            "with authorities of third countries on the EU AML high-risk list."
        ),
        "criticality": "important",
        "applicable_entity": "EBA / EIOPA / ESMA",
    },
    {
        "article": "Article 1 / Art 45b (coordination groups)",
        "requirement_text": (
            "The Management Board may set up coordination groups on defined topics (and must "
            "do so at the request of five Board of Supervisors members). All competent "
            "authorities shall participate and provide the necessary information."
        ),
        "criticality": "informational",
        "applicable_entity": "ESAs / national competent authorities",
    },
    {
        "article": "Recitals 7 to 10 (sustainable finance and fintech)",
        "requirement_text": (
            "The ESAs shall identify and report risks that environmental, social and "
            "governance (ESG) factors pose to financial stability, consider those risks when "
            "coordinating Union-wide stress tests, provide guidance on embedding sustainability "
            "in EU financial legislation, and strengthen their oversight of technological "
            "innovation (fintech)."
        ),
        "criticality": "important",
        "applicable_entity": "EBA / EIOPA / ESMA",
    },
    {
        "article": "Article 4 / MiFIR (ESMA supervises DRSPs)",
        "requirement_text": (
            "From 1 January 2022, authorisation and supervision of data reporting services "
            "providers (approved publication arrangements, consolidated tape providers, "
            "approved reporting mechanisms), except those benefiting from a derogation, "
            "transfer from national competent authorities to ESMA, which gains direct "
            "data-gathering powers, investigation and on-site inspection powers, and the power "
            "to impose fines and periodic penalty payments."
        ),
        "criticality": "critical",
        "applicable_entity": "ESMA / data reporting services providers",
    },
    {
        "article": "Article 5 / Benchmarks (ESMA critical bmarks)",
        "requirement_text": (
            "From 1 January 2022, certain critical benchmarks are supervised at Union level by "
            "ESMA, and ESMA becomes the single authority recognising third-country benchmark "
            "administrators, replacing the Member-State-of-reference procedure."
        ),
        "criticality": "important",
        "applicable_entity": "ESMA / benchmark administrators",
    },
]


def main():
    db = SessionLocal()
    try:
        existing = db.query(LawRequirement).filter(LawRequirement.law_id == ESAS_LAW_ID).count()
        if existing:
            print(f"[INFO] {existing} requirements already exist for law_id={ESAS_LAW_ID}. Skipping.")
            return
        for r in REQUIREMENTS:
            db.add(LawRequirement(
                law_id=ESAS_LAW_ID,
                cluster_id=ESAS_CLUSTER_ID,
                article=r["article"],
                requirement_text=r["requirement_text"],
                criticality=r["criticality"],
                applicable_entity=r["applicable_entity"],
            ))
        db.commit()
        print(f"[OK] seeded {len(REQUIREMENTS)} requirements for law_id={ESAS_LAW_ID}, cluster_id={ESAS_CLUSTER_ID}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
