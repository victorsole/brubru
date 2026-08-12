"""Seed the canonical headline obligations of Regulation (EU) 2024/1781 (ESPR,
the Ecodesign for Sustainable Products Regulation) into law_requirements.

Pre-curated from a sequential read of the Regulation (Articles 1-80, 14 Chapters)
- Brubru canon project, 12 August 2026. Most substantive ecodesign requirements
bite product-group by product-group as delegated acts are adopted under Article
4, so many rows carry no fixed deadline; the destruction-of-unsold-goods ban and
the DPP registry are the hard-dated exceptions.

IDs after create_law_clusters.py --package espr_ecodesign_regulation:
  SELECT id, celex FROM eu_laws WHERE celex='32024R1781'; -> 11447
  SELECT id, name FROM law_clusters WHERE name LIKE 'ESPR%'; -> 63
"""
import sys
from datetime import date
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from core.database import SessionLocal
from models.eu_law import LawRequirement

ESPR_LAW_ID = 11447
ESPR_CLUSTER_ID = 63

REQUIREMENTS = [
    {"article": "Art 3", "criticality": "high", "applicable_entity": "Member State", "deadline": None,
     "requirement_text": "Do not restrict, prohibit or impede the market access of a product that complies with EU-level ecodesign performance and information requirements on national-requirement grounds. Once the EU sets a requirement for a product group, Member States lose the power to set conflicting national rules."},
    {"article": "Art 4 / 8", "criticality": "critical", "applicable_entity": "European Commission", "deadline": None,
     "requirement_text": "Any product-group ecodesign requirement must be adopted by delegated act specifying at minimum the elements in Article 8: the product group definition, the performance and information requirements, test methods, the conformity assessment module, a transitional period, and a review date. A first delegated act cannot apply before 19 July 2025 and requirements carry at least an 18-month lead time."},
    {"article": "Art 9", "criticality": "critical", "applicable_entity": "manufacturer / economic operator", "deadline": None,
     "requirement_text": "A covered product cannot be placed on the market or put into service unless a Digital Product Passport is available and its data is accurate, complete and up to date, connected through a data carrier to the unique product identifier."},
    {"article": "Art 10", "criticality": "high", "applicable_entity": "economic operator placing the product on the market", "deadline": None,
     "requirement_text": "Provide dealers and online marketplaces a digital copy of the DPP data carrier within 5 working days of request, and keep a back-up copy of the digital product passport through a DPP service provider."},
    {"article": "Art 13", "criticality": "high", "applicable_entity": "economic operator placing the product on the market", "deadline": date(2026, 7, 19),
     "requirement_text": "Upload the required unique identifiers, and where relevant the commodity code, to the central Digital Product Passport registry. The registry must be operational by 19 July 2026."},
    {"article": "Art 15", "criticality": "medium", "applicable_entity": "importer / customs declarant", "deadline": None,
     "requirement_text": "Provide the unique registration identifier to customs authorities when releasing a covered product for free circulation."},
    {"article": "Art 16-17", "criticality": "medium", "applicable_entity": "economic operator", "deadline": None,
     "requirement_text": "Do not place on the market products bearing labels that mimic or could confuse customers about an official ESPR label."},
    {"article": "Art 21", "criticality": "low", "applicable_entity": "economic operator (self-regulation signatory)", "deadline": None,
     "requirement_text": "A self-regulation measure recognised as an alternative to a delegated act must keep its monitoring plan, ecodesign requirements and signatory list current and publicly accessible, and its signatories must hold at least 80 percent of the market by volume."},
    {"article": "Art 24", "criticality": "high", "applicable_entity": "economic operator (excl. micro and small)", "deadline": date(2027, 7, 19),
     "requirement_text": "Disclose annually, on an easily accessible webpage, the volume, reasons and end-of-life treatment of unsold consumer products discarded. First consolidated reporting from 19 July 2027, then every 36 months. Micro and small enterprises are exempt; medium enterprises join from 19 July 2030."},
    {"article": "Art 25", "criticality": "critical", "applicable_entity": "economic operator (excl. micro and small)", "deadline": date(2026, 7, 19),
     "requirement_text": "Do not destroy unsold consumer products listed in Annex VII, starting with textiles and footwear, from 19 July 2026. Medium enterprises are covered from 19 July 2030; micro and small enterprises are exempt. Derogations are narrow and must be documented."},
    {"article": "Art 27", "criticality": "critical", "applicable_entity": "manufacturer", "deadline": None,
     "requirement_text": "Carry out the specified conformity assessment procedure, draw up the EU declaration of conformity, affix the CE marking, and retain the technical documentation for 10 years after the product is placed on the market."},
    {"article": "Art 27(7)", "criticality": "medium", "applicable_entity": "manufacturer", "deadline": None,
     "requirement_text": "Provide digital instructions in an easily understood language, accessible online for at least 10 years after placing on the market, and provide safety information on paper."},
    {"article": "Art 27(8)", "criticality": "high", "applicable_entity": "manufacturer", "deadline": None,
     "requirement_text": "Take corrective action, withdraw or recall a non-compliant product without undue delay and notify the market surveillance authorities."},
    {"article": "Art 29", "criticality": "high", "applicable_entity": "importer", "deadline": None,
     "requirement_text": "Verify manufacturer compliance, including the conformity assessment, technical documentation and information and DPP availability, before placing a product on the market."},
    {"article": "Art 30", "criticality": "medium", "applicable_entity": "distributor", "deadline": None,
     "requirement_text": "Verify CE marking, required documentation and labelling before making a product available on the market."},
    {"article": "Art 31", "criticality": "medium", "applicable_entity": "dealer", "deadline": None,
     "requirement_text": "Ensure the digital product passport and required labels are easily accessible to customers, including in distance selling."},
    {"article": "Art 35", "criticality": "medium", "applicable_entity": "provider of an online marketplace", "deadline": None,
     "requirement_text": "Cooperate with market surveillance authorities and maintain a single contact point for compliance matters."},
    {"article": "Art 40", "criticality": "high", "applicable_entity": "economic operator", "deadline": None,
     "requirement_text": "Do not design products to detect testing and alter their behaviour accordingly, and do not push software or firmware updates that worsen regulated performance without the explicit consent of the customer."},
    {"article": "Art 65", "criticality": "medium", "applicable_entity": "contracting authority / contracting entity", "deadline": None,
     "requirement_text": "Award public contracts for covered products, works or services complying with the minimum green public procurement requirements set by the Commission by implementing act."},
    {"article": "Art 74", "criticality": "medium", "applicable_entity": "Member State", "deadline": None,
     "requirement_text": "Lay down effective, proportionate and dissuasive penalties for infringements, including fines and time-limited exclusion from public procurement."},
]

db = SessionLocal()
try:
    from sqlalchemy import text as _text
    n = db.execute(_text("DELETE FROM law_requirements WHERE law_id=:l AND cluster_id=:c"),
                   {"l": ESPR_LAW_ID, "c": ESPR_CLUSTER_ID}).rowcount
    if n:
        print(f"[purge] removed {n} prior ESPR requirements")
    for r in REQUIREMENTS:
        db.add(LawRequirement(
            law_id=ESPR_LAW_ID, cluster_id=ESPR_CLUSTER_ID,
            article=r["article"][:50], requirement_text=r["requirement_text"],
            deadline=r.get("deadline"), criticality=r["criticality"],
            applicable_entity=r["applicable_entity"][:100],
            extra_metadata={"source": "canon_curated_seed", "seeded_at": "2026-08-12"},
        ))
    db.commit()
    print(f"[seeded] {len(REQUIREMENTS)} ESPR requirements into law_requirements")
finally:
    db.close()
