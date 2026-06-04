"""Seed the canonical headline obligations of Regulation (EU) 2024/1689 (AI Act) into
law_requirements. Pre-curated from a full top-to-bottom read of the recitals, operative
articles and Annexes (data/canon/2024-1689_aiact.analysis.md). article and
applicable_entity are VARCHAR(50).

ids verified live against prod Supabase on 26 May 2026:
  eu_laws id for 32024R1689 -> 28664 (ingested via canon pipeline)
  law_clusters 'AI Act Package' -> 4
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root)); sys.path.insert(0, str(project_root / "backend"))
from dotenv import load_dotenv
load_dotenv(project_root / ".env")
from backend.core.database import SessionLocal
from backend.models.eu_law import LawRequirement

AIACT_LAW_ID = 28664
AIACT_CLUSTER_ID = 4

REQUIREMENTS = [
    {"article": "Article 5 (prohibited practices)",
     "requirement_text": "Eight AI practices are prohibited: subliminal, manipulative or deceptive techniques causing significant harm; exploitation of vulnerabilities (age, disability, social or economic situation); social scoring; predictive policing of individuals based solely on profiling; untargeted scraping of facial images from the internet or CCTV; emotion recognition in the workplace and education; biometric categorisation by sensitive attributes; and real-time remote biometric identification in public spaces for law enforcement save three narrow, judicially authorised exceptions.",
     "criticality": "critical", "applicable_entity": "all operators"},
    {"article": "Article 6 (high-risk classification)",
     "requirement_text": "An AI system is high-risk if it is a safety component of, or is, a product covered by the Annex I product-safety legislation requiring third-party conformity assessment, or if it falls within one of the eight Annex III areas. The Article 6(3) derogation may exclude an Annex III system that poses no significant risk, but never one that performs profiling of natural persons.",
     "criticality": "critical", "applicable_entity": "providers"},
    {"article": "Article 9 (risk management system)",
     "requirement_text": "Providers of high-risk AI systems must establish, implement, document and maintain a continuous, iterative risk-management system across the entire lifecycle, identifying and mitigating risks to health, safety and fundamental rights.",
     "criticality": "critical", "applicable_entity": "high-risk providers"},
    {"article": "Article 10 (data and data governance)",
     "requirement_text": "Training, validation and testing data sets for high-risk AI systems must be subject to appropriate data-governance practices and be relevant, sufficiently representative and, to the best extent possible, free of errors and complete, with attention to bias mitigation.",
     "criticality": "important", "applicable_entity": "high-risk providers"},
    {"article": "Articles 11 to 12 (documentation, logs)",
     "requirement_text": "High-risk AI systems require technical documentation drawn up before placing on the market (Annex IV) and kept up to date, plus automatic recording of events (logs) over the system's lifetime to ensure traceability.",
     "criticality": "important", "applicable_entity": "high-risk providers"},
    {"article": "Articles 13 to 14 (transparency, oversight)",
     "requirement_text": "High-risk AI systems must be transparent to deployers, accompanied by instructions for use, and designed to allow effective human oversight by natural persons throughout their use.",
     "criticality": "critical", "applicable_entity": "high-risk providers"},
    {"article": "Article 15 (accuracy, cybersecurity)",
     "requirement_text": "High-risk AI systems must achieve an appropriate level of accuracy, robustness and cybersecurity consistent with the state of the art, and perform consistently throughout their lifecycle.",
     "criticality": "important", "applicable_entity": "high-risk providers"},
    {"article": "Article 16 (provider obligations)",
     "requirement_text": "Providers of high-risk AI systems must operate a quality management system, draw up documentation, carry out the conformity assessment, affix the CE marking, register the system in the EU database and conduct post-market monitoring.",
     "criticality": "critical", "applicable_entity": "high-risk providers"},
    {"article": "Articles 26 to 27 (deployer duties)",
     "requirement_text": "Deployers of high-risk AI systems must use them per the instructions, ensure human oversight and monitoring, and (public bodies, public-service providers, banking and insurance) carry out a fundamental rights impact assessment before deployment.",
     "criticality": "important", "applicable_entity": "high-risk deployers"},
    {"article": "Article 43 + 49 (conformity, register)",
     "requirement_text": "High-risk AI systems must undergo conformity assessment (provider self-assessment as a rule; notified-body assessment for certain biometric systems) and be registered in the public EU database before being placed on the market.",
     "criticality": "important", "applicable_entity": "high-risk providers"},
    {"article": "Article 50 (transparency duties)",
     "requirement_text": "Users must be told when interacting with an AI system (chatbots); AI-generated synthetic content must be marked machine-readable; persons exposed to emotion-recognition or biometric-categorisation systems must be informed; and deepfakes and public-interest AI-generated text must be labelled.",
     "criticality": "important", "applicable_entity": "providers and deployers"},
    {"article": "Article 53 (GPAI model duties)",
     "requirement_text": "Providers of general-purpose AI models must keep technical documentation (Annex XI), inform downstream providers (Annex XII), put in place a policy to comply with Union copyright law honouring the text-and-data-mining opt-out, and publish a summary of the content used for training.",
     "criticality": "critical", "applicable_entity": "GPAI model providers"},
    {"article": "Articles 51 to 52 (systemic risk)",
     "requirement_text": "A general-purpose AI model is classified as having systemic risk when its cumulative training compute exceeds 10^25 floating-point operations or by Commission decision on the Annex XIII criteria; the provider must notify the AI Office within two weeks of meeting or expecting to meet the threshold.",
     "criticality": "important", "applicable_entity": "GPAI model providers"},
    {"article": "Article 55 (systemic-risk duties)",
     "requirement_text": "Providers of general-purpose AI models with systemic risk must perform model evaluation including adversarial testing (red-teaming), assess and mitigate systemic risks, report serious incidents to the AI Office, and ensure an adequate level of cybersecurity.",
     "criticality": "critical", "applicable_entity": "systemic-risk GPAI providers"},
    {"article": "Article 57 (regulatory sandbox)",
     "requirement_text": "Each Member State must ensure at least one AI regulatory sandbox is established and operational by 2 August 2026, giving priority and simplified conditions to SMEs and start-ups, with a regime for testing in real-world conditions.",
     "criticality": "informational", "applicable_entity": "Member States"},
    {"article": "Article 99 (penalties)",
     "requirement_text": "Infringements carry administrative fines up to EUR 35 000 000 or 7% of worldwide annual turnover for prohibited practices, up to EUR 15 000 000 or 3% for other obligations, and up to EUR 7 500 000 or 1% for incorrect or misleading information; GPAI model providers face up to EUR 15 000 000 or 3% (Article 101).",
     "criticality": "critical", "applicable_entity": "all operators"},
    {"article": "Article 113 (application dates)",
     "requirement_text": "The Regulation entered into force on 1 August 2024 and applies from 2 August 2026; prohibitions and general provisions apply from 2 February 2025; GPAI-model rules, governance and penalties from 2 August 2025; Annex I product-related high-risk systems from 2 August 2027.",
     "criticality": "informational", "applicable_entity": "all operators"},
]


def main():
    db = SessionLocal()
    try:
        if db.query(LawRequirement).filter(LawRequirement.law_id == AIACT_LAW_ID).count():
            print("[INFO] requirements already exist. Skipping."); return
        bad = [r["article"] for r in REQUIREMENTS if len(r["article"]) > 50] + \
              [r["applicable_entity"] for r in REQUIREMENTS if len(r["applicable_entity"]) > 50]
        if bad:
            print("ABORT: >50 chars:", bad); sys.exit(1)
        for r in REQUIREMENTS:
            db.add(LawRequirement(law_id=AIACT_LAW_ID, cluster_id=AIACT_CLUSTER_ID,
                   article=r["article"], requirement_text=r["requirement_text"],
                   criticality=r["criticality"], applicable_entity=r["applicable_entity"]))
        db.commit()
        print(f"[OK] seeded {len(REQUIREMENTS)} requirements for law_id={AIACT_LAW_ID}, cluster_id={AIACT_CLUSTER_ID}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
