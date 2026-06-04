"""Seed the canonical headline obligations of Regulation (EU) 2017/625 (the Official
Controls Regulation) into law_requirements. Pre-curated from a full top-to-bottom read
(data/canon/2017-625_official_controls.analysis.md). article and applicable_entity are
VARCHAR(50).

ids verified live against prod Supabase on 26 May 2026:
  eu_laws id for 32017R0625 -> 4529
  law_clusters 'Official Controls Regulation...' -> 29
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root)); sys.path.insert(0, str(project_root / "backend"))
from dotenv import load_dotenv
load_dotenv(project_root / ".env")
from backend.core.database import SessionLocal
from backend.models.eu_law import LawRequirement

LAW_ID = 4529
CLUSTER_ID = 29

REQUIREMENTS = [
    {"article": "Article 1(2) (scope, ten areas)",
     "requirement_text": "Official controls verify compliance across ten areas: food and food safety (incl. food-contact materials); GMOs for food and feed production; feed and feed safety; animal health; animal by-products; animal welfare; plant health; plant protection products and sustainable pesticide use; organic production and labelling; and PDO, PGI and TSG.",
     "criticality": "informational", "applicable_entity": "competent authorities"},
    {"article": "Article 4 (competent authorities)",
     "requirement_text": "Member States must designate competent authorities for every area in scope, adequately resourced, impartial and professional, plus a single authority for coordinated communication with other Member States and the Commission.",
     "criticality": "critical", "applicable_entity": "Member States"},
    {"article": "Article 9 (risk-based controls)",
     "requirement_text": "Competent authorities must perform official controls regularly, on a risk basis and at appropriate frequency, on all operators, activities, animals and goods, generally without prior notice, taking account of the likelihood of fraud.",
     "criticality": "critical", "applicable_entity": "competent authorities"},
    {"article": "Articles 13 to 15 (records, cooperation)",
     "requirement_text": "Official controls must be documented in writing, with a copy given to the operator on request; operators must cooperate with and grant access to competent authorities and provide the information needed to identify themselves and their suppliers and customers.",
     "criticality": "important", "applicable_entity": "operators / authorities"},
    {"article": "Articles 28 to 33 (delegation)",
     "requirement_text": "Competent authorities may delegate certain control tasks to bodies accredited to the relevant ISO standard, or to natural persons, only under conditions preserving impartiality, quality and consistency.",
     "criticality": "informational", "applicable_entity": "competent authorities"},
    {"article": "Articles 34 to 42 (labs, second opinion)",
     "requirement_text": "Samples must be analysed by official laboratories accredited to EN ISO/IEC 17025; operators whose animals or goods are sampled have a right to a second expert opinion at their own expense; mystery shopping may be used for online trade.",
     "criticality": "important", "applicable_entity": "official laboratories"},
    {"article": "Title II Ch V (border control posts)",
     "requirement_text": "Animals and goods entering the Union from third countries must be presented at designated border control posts for documentary, identity and physical checks before release for free circulation, at risk-based frequencies.",
     "criticality": "critical", "applicable_entity": "importers / authorities"},
    {"article": "Common Health Entry Document (CHED)",
     "requirement_text": "Each consignment requiring border controls must travel with a Common Health Entry Document used for prior notification, to record the control outcome and to obtain customs clearance once controls are complete.",
     "criticality": "important", "applicable_entity": "importers"},
    {"article": "Articles 78 to 83 (mandatory fees)",
     "requirement_text": "Competent authorities must collect mandatory fees or charges for the controls listed in Annex IV Chapter II and for border controls, either at cost or at the Annex IV amounts; fees must cover but not exceed costs, be transparent, and not be refunded.",
     "criticality": "important", "applicable_entity": "operators / authorities"},
    {"article": "Articles 86 to 91 (certification)",
     "requirement_text": "Official certificates and attestations (including plant passports, organic logos, identification marks and PDO/PGI marks) must be issued under common reliability rules by competent authorities or certifying officers.",
     "criticality": "important", "applicable_entity": "operators / authorities"},
    {"article": "Articles 92 to 101 (reference labs)",
     "requirement_text": "The Commission designates EU reference laboratories per sector and EU reference centres for the authenticity and integrity of the agri-food chain and for animal welfare; these apply from 29 April 2018.",
     "criticality": "informational", "applicable_entity": "EU / national reference labs"},
    {"article": "IMSOC + admin assistance",
     "requirement_text": "Official controls run on a single computerised system (IMSOC) integrating TRACES and RASFF; Member States designate liaison bodies for cross-border administrative assistance to pursue non-compliance and fraud across borders.",
     "criticality": "informational", "applicable_entity": "Member States / Commission"},
    {"article": "MANCP + annual reports",
     "requirement_text": "Each Member State must set up and update a risk-based multi-annual national control plan (MANCP) covering all areas in scope, coordinated by a single body, and submit an annual report to the Commission.",
     "criticality": "informational", "applicable_entity": "Member States"},
    {"article": "Article 139 (penalties)",
     "requirement_text": "Member States must lay down effective, proportionate and dissuasive penalties; for violations through fraudulent or deceptive practices, financial penalties must reflect at least the operator's economic advantage or a percentage of turnover.",
     "criticality": "critical", "applicable_entity": "Member States / operators"},
    {"article": "Article 140 (whistleblower)",
     "requirement_text": "Member States must ensure effective mechanisms for reporting actual or potential infringements, with protection of reporting persons against retaliation, discrimination and other unfair treatment, and protection of their personal data.",
     "criticality": "informational", "applicable_entity": "Member States"},
    {"article": "Article 167 (application dates)",
     "requirement_text": "The Regulation entered into force on 27 April 2017 and applies from 14 December 2019; EU reference laboratory provisions (Articles 92 to 101) apply from 29 April 2018; certain plant-health provisions from 29 April 2022.",
     "criticality": "informational", "applicable_entity": "all operators / authorities"},
]


def main():
    db = SessionLocal()
    try:
        if db.query(LawRequirement).filter(LawRequirement.law_id == LAW_ID).count():
            print("[INFO] requirements already exist. Skipping."); return
        bad = [r["article"] for r in REQUIREMENTS if len(r["article"]) > 50] + \
              [r["applicable_entity"] for r in REQUIREMENTS if len(r["applicable_entity"]) > 50]
        if bad:
            print("ABORT: >50 chars:", bad); sys.exit(1)
        for r in REQUIREMENTS:
            db.add(LawRequirement(law_id=LAW_ID, cluster_id=CLUSTER_ID,
                   article=r["article"], requirement_text=r["requirement_text"],
                   criticality=r["criticality"], applicable_entity=r["applicable_entity"]))
        db.commit()
        print(f"[OK] seeded {len(REQUIREMENTS)} requirements for law_id={LAW_ID}, cluster_id={CLUSTER_ID}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
