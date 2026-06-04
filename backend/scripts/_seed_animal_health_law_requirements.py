"""Seed the canonical headline obligations of Regulation (EU) 2016/429 (Animal Health Law)
into law_requirements. Pre-curated from a full top-to-bottom read of the regulation + the
analysis at data/canon/2016-429_animal_health_law.analysis.md (Brubru canon project, May 2026).

NOTE: law_requirements.article and .applicable_entity are VARCHAR(50). Keep both <= 50 chars.

ids verified live against prod Supabase on 25 May 2026:
  SELECT id, celex FROM eu_laws WHERE celex='32016R0429';  -> 17658
  SELECT id, name FROM law_clusters WHERE name LIKE 'Animal Health Law%';  -> 26
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

AHL_LAW_ID = 17658
AHL_CLUSTER_ID = 26

REQUIREMENTS = [
    {
        "article": "Article 10 (operator responsibilities)",
        "requirement_text": (
            "Operators are primarily responsible for the health of their kept animals, the "
            "prudent and responsible use of veterinary medicines, minimising disease spread, "
            "and good animal husbandry, and must apply appropriate biosecurity measures "
            "(physical and management) proportionate to the species, production type and risks."
        ),
        "criticality": "critical",
        "applicable_entity": "operators / animal keepers",
    },
    {
        "article": "Article 11 (animal health knowledge)",
        "requirement_text": (
            "Operators and animal professionals must have adequate knowledge of animal "
            "diseases (including zoonoses), biosecurity principles, the animal-health / animal-"
            "welfare / human-health interaction, good husbandry, and antimicrobial resistance."
        ),
        "criticality": "important",
        "applicable_entity": "operators / animal professionals",
    },
    {
        "article": "Article 18 (notification of disease)",
        "requirement_text": (
            "Operators and other relevant persons must immediately notify the competent "
            "authority on suspicion or detection of a notifiable listed disease, and notify a "
            "veterinarian of abnormal mortalities or other signs of serious disease for "
            "further investigation."
        ),
        "criticality": "critical",
        "applicable_entity": "operators / vets / keepers",
    },
    {
        "article": "Article 24 (operators' surveillance)",
        "requirement_text": (
            "Operators must observe the health and behaviour of their animals, watch for "
            "changes in production parameters, and look for abnormal mortalities and other "
            "signs of serious disease, to detect listed and emerging diseases."
        ),
        "criticality": "important",
        "applicable_entity": "operators / animal keepers",
    },
    {
        "article": "Article 25 (animal health visits)",
        "requirement_text": (
            "Operators must ensure their establishments receive animal health visits from a "
            "veterinarian at frequencies proportionate to the risk, for disease prevention and "
            "early detection of listed or emerging diseases."
        ),
        "criticality": "important",
        "applicable_entity": "operators / establishments",
    },
    {
        "article": "Article 84 (registration of establishments)",
        "requirement_text": (
            "Operators of establishments keeping terrestrial animals or handling germinal "
            "products must register with the competent authority before commencing activity, "
            "providing details of location, species, numbers and establishment type; the "
            "authority assigns a unique registration number (Article 93)."
        ),
        "criticality": "critical",
        "applicable_entity": "operators / establishments",
    },
    {
        "article": "Article 94 (approval of establishments)",
        "requirement_text": (
            "Higher-risk establishments must obtain prior approval before operating: assembly "
            "operations for ungulates and poultry moved between Member States, germinal product "
            "establishments, hatcheries, and certain poultry establishments. Approval follows "
            "an on-site visit (Articles 96 to 99)."
        ),
        "criticality": "critical",
        "applicable_entity": "operators / establishments",
    },
    {
        "article": "Articles 102 to 105 (record-keeping)",
        "requirement_text": (
            "Operators of registered or approved establishments, germinal product "
            "establishments, transporters and assembly operators must keep records (species, "
            "numbers, movements, mortality, biosecurity, treatments) and retain them for a "
            "minimum period set by the competent authority, not less than three years."
        ),
        "criticality": "important",
        "applicable_entity": "operators / transporters",
    },
    {
        "article": "Articles 112 to 115 (identification)",
        "requirement_text": (
            "Operators must identify and register kept animals per species: bovine animals by "
            "individual physical identification plus an identification document; ovine and "
            "caprine by physical means plus movement document; equine by a unique code plus a "
            "single lifetime identification document; porcine at establishment level. Data go "
            "to the national computer database (Article 109)."
        ),
        "criticality": "critical",
        "applicable_entity": "operators / animal keepers",
    },
    {
        "article": "Articles 124 to 126 (movements in Union)",
        "requirement_text": (
            "Operators may only move kept terrestrial animals within and between Member States "
            "if the animals come from registered or approved establishments, meet "
            "identification and registration requirements, show no disease symptoms, and are "
            "not subject to movement restrictions or located in a restricted zone."
        ),
        "criticality": "critical",
        "applicable_entity": "operators / transporters",
    },
    {
        "article": "Article 143 (animal health certificate)",
        "requirement_text": (
            "Operators may only move ungulates, poultry and certain other animals to another "
            "Member State if accompanied by an animal health certificate issued and signed by "
            "an official veterinarian of the Member State of origin; otherwise a self-"
            "declaration document is required (Article 151)."
        ),
        "criticality": "critical",
        "applicable_entity": "operators / official vets",
    },
    {
        "article": "Articles 152 to 153 (movement notification)",
        "requirement_text": (
            "Operators must notify the competent authority in advance of certified cross-"
            "border movements; the authority notifies the Member State of destination, "
            "wherever possible through the TRACES integrated computerised veterinary system."
        ),
        "criticality": "important",
        "applicable_entity": "operators / competent authority",
    },
    {
        "article": "Article 229 (entry into the Union)",
        "requirement_text": (
            "Animals, germinal products and products of animal origin may enter the Union only "
            "from a listed third country or territory, from approved establishments where "
            "required, meeting animal health requirements as stringent as intra-Union rules, "
            "and accompanied by an animal health certificate (Article 237)."
        ),
        "criticality": "critical",
        "applicable_entity": "importers / EU operators",
    },
    {
        "article": "Article 246 (pet movements)",
        "requirement_text": (
            "A maximum of five pet animals of the Annex I Part A species (dogs, cats, ferrets) "
            "may travel in a single non-commercial movement, with an exception for "
            "competitions and exhibitions (animals over six months old, registered). Pets must "
            "be identified, meet preventive measures (rabies vaccination) and carry an "
            "identification document (the EU pet passport) (Articles 247 to 250)."
        ),
        "criticality": "important",
        "applicable_entity": "pet keepers / travellers",
    },
    {
        "article": "Article 257 (emergency measures)",
        "requirement_text": (
            "On an outbreak of a listed or emerging disease or a hazard posing a serious risk, "
            "the competent authority must immediately take emergency disease-control measures "
            "(movement restrictions, quarantine, surveillance, traceability and control "
            "measures) and inform the Commission and other Member States."
        ),
        "criticality": "critical",
        "applicable_entity": "competent authority",
    },
    {
        "article": "Article 268 (penalties)",
        "requirement_text": (
            "Member States must lay down effective, proportionate and dissuasive penalties for "
            "infringements of the Regulation and take all measures necessary to ensure they "
            "are implemented (notified to the Commission by 22 April 2022)."
        ),
        "criticality": "informational",
        "applicable_entity": "Member States",
    },
]


def main():
    db = SessionLocal()
    try:
        existing = db.query(LawRequirement).filter(LawRequirement.law_id == AHL_LAW_ID).count()
        if existing:
            print(f"[INFO] {existing} requirements already exist for law_id={AHL_LAW_ID}. Skipping.")
            return
        bad = [r["article"] for r in REQUIREMENTS if len(r["article"]) > 50] + \
              [r["applicable_entity"] for r in REQUIREMENTS if len(r["applicable_entity"]) > 50]
        if bad:
            print("ABORT: values exceed VARCHAR(50):", bad)
            sys.exit(1)
        for r in REQUIREMENTS:
            db.add(LawRequirement(
                law_id=AHL_LAW_ID,
                cluster_id=AHL_CLUSTER_ID,
                article=r["article"],
                requirement_text=r["requirement_text"],
                criticality=r["criticality"],
                applicable_entity=r["applicable_entity"],
            ))
        db.commit()
        print(f"[OK] seeded {len(REQUIREMENTS)} requirements for law_id={AHL_LAW_ID}, cluster_id={AHL_CLUSTER_ID}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
