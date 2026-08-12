"""Seed the canonical headline obligations of Regulation (EU) 2025/2509 (the Toy
Safety Regulation) into law_requirements.

Pre-curated from a sequential read of the Regulation (59 Articles, 11 Chapters,
Annexes I-VIII) - Brubru canon project, 12 August 2026. Annex-only chemical
limits are not asserted here.

NOTE: the Digital Product Passport regime acts share ONE EU Law Comply hub
cluster (id 65, "EU Digital Product Passport regime (ESPR + product laws)"), not
a per-law cluster. The toy law's requirements seed into cluster 65.
  SELECT id, celex FROM eu_laws WHERE celex='32025R2509'; -> 28684
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

TOYS_LAW_ID = 28684
DPP_HUB_CLUSTER_ID = 65

R = [
    ("Art 5", "critical", "manufacturer", date(2030, 8, 1),
     "Ensure the toy meets the general safety requirement and the Annex II particular safety requirements before placing it on the market, including the tighter chemical rules on carcinogenic, mutagenic and reprotoxic substances, endocrine disruptors, PFAS and bisphenols."),
    ("Art 6", "high", "manufacturer", date(2030, 8, 1),
     "Affix the required warnings (age, ability, weight, supervision) in the format and language rules set out in Annex III."),
    ("Art 7(2)", "critical", "manufacturer", date(2030, 8, 1),
     "Draw up technical documentation and carry out the applicable conformity assessment procedure before placing a toy on the market."),
    ("Art 7(2)", "critical", "manufacturer", date(2030, 8, 1),
     "Create the digital product passport, affix the data carrier, affix the CE marking, and upload the identifiers to the registry before placing the toy on the market."),
    ("Art 7(3)", "high", "manufacturer", None,
     "Keep the technical documentation and the digital product passport for 10 years after the toy is placed on the market."),
    ("Art 7(9)", "high", "manufacturer", None,
     "Take corrective action and, where a toy presents a risk, inform market surveillance authorities via the Safety Business Gateway."),
    ("Art 8(3)", "medium", "authorised representative", None,
     "Perform the mandated tasks under a written authorisation, at minimum keeping the technical documentation and the digital product passport available for 10 years."),
    ("Art 9(2)", "high", "importer", date(2030, 8, 1),
     "Verify the conformity assessment, technical documentation, digital product passport, data carrier, registry upload and CE marking before placing a toy on the market."),
    ("Art 10(2)", "medium", "distributor", date(2030, 8, 1),
     "Verify the instructions, warnings, the data carrier and the CE marking before making a toy available on the market."),
    ("Art 11", "medium", "fulfilment service provider", None,
     "Ensure warehousing, packaging and dispatch conditions do not jeopardise the essential safety requirements, and refuse to support a suspected non-compliant toy."),
    ("Art 12(1)", "high", "person placing or modifying under own name", None,
     "Assume full manufacturer obligations where placing a toy under own name or trademark, or carrying out a substantial modification."),
    ("Art 13", "medium", "all economic operators", None,
     "Identify the upstream and downstream supply-chain operators on request, for 10 years."),
    ("Art 14", "high", "online marketplace", None,
     "Comply with Digital Services Act Articles 30 to 32 and General Product Safety Regulation Article 22, and design the online interface to display the CE marking, warnings and digital product passport access before purchase."),
    ("Art 18", "critical", "manufacturer", date(2030, 8, 1),
     "Affix the CE marking visibly, legibly and indelibly before the toy is placed on the market."),
    ("Art 19", "critical", "manufacturer", date(2030, 8, 1),
     "Create a digital product passport meeting the Annex VI content requirements before placing a toy on the market, and keep it available for 10 years."),
    ("Art 22(1)", "high", "economic operator placing the toy on the market", date(2030, 8, 1),
     "Upload the unique product identifier and the unique operator identifier to the digital product passport registry before placing a toy on the market."),
    ("Art 23(2)", "medium", "importer / declarant", None,
     "Provide the unique registration identifier to customs authorities when placing an imported toy under the free-circulation procedure, verified through the EU CSW-CERTEX customs interconnection."),
    ("Art 25", "critical", "manufacturer", date(2030, 8, 1),
     "Carry out a safety assessment covering all chemical, physical, mechanical, electrical, flammability, hygiene and radioactivity hazards before placing a toy on the market."),
    ("Art 32 / 40", "high", "notified body", None,
     "Meet the independence, competence and impartiality requirements, and carry out EU-type examination tasks in accordance with Annex IV."),
    ("Art 55", "medium", "Member State", date(2028, 8, 1),
     "Lay down effective, proportionate and dissuasive penalties for infringements, and notify the Commission by 1 August 2028."),
]

db = SessionLocal()
try:
    from sqlalchemy import text as _t
    n = db.execute(_t("DELETE FROM law_requirements WHERE law_id=:l AND cluster_id=:c"),
                   {"l": TOYS_LAW_ID, "c": DPP_HUB_CLUSTER_ID}).rowcount
    if n:
        print(f"[purge] removed {n} prior Toy Safety requirements")
    for art, crit, ent, dl, txt in R:
        db.add(LawRequirement(
            law_id=TOYS_LAW_ID, cluster_id=DPP_HUB_CLUSTER_ID,
            article=art[:50], requirement_text=txt, deadline=dl,
            criticality=crit, applicable_entity=ent[:100],
            extra_metadata={"source": "canon_curated_seed", "seeded_at": "2026-08-12"},
        ))
    db.commit()
    print(f"[seeded] {len(R)} Toy Safety requirements into hub cluster {DPP_HUB_CLUSTER_ID}")
finally:
    db.close()
