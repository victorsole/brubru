"""Seed the canonical headline obligations of Regulation (EU) 2024/1252 (CRMA,
the Critical Raw Materials Act) into law_requirements.

Pre-curated from a sequential read of the Regulation (Articles 1-49, 9 Chapters)
- Brubru canon project, 12 August 2026. Annex-only figures (the strategic and
critical raw-material lists) were flagged by the reader and are not asserted here.

IDs after create_law_clusters.py --package crma_critical_raw_materials_act:
  SELECT id, celex FROM eu_laws WHERE celex='32024R1252'; -> 19056
  SELECT id, name FROM law_clusters WHERE name LIKE 'CRMA%'; -> 64
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

CRMA_LAW_ID = 19056
CRMA_CLUSTER_ID = 64

R = [
    ("Art 3-4", "critical", "European Commission", date(2027, 5, 24),
     "Maintain and, by 24 May 2027 and every 3 years thereafter, review and if necessary update the lists of strategic and critical raw materials (Annexes I and II)."),
    ("Art 5(1)", "critical", "Member State / European Commission", date(2030, 12, 31),
     "Work towards the 2030 capacity benchmarks for strategic raw materials measured against EU annual consumption: at least 10 percent from Union extraction, at least 40 percent from Union processing, at least 25 percent from recycling, and no more than 65 percent of annual consumption of each strategic raw material from a single third country."),
    ("Art 6-7", "high", "project promoter (company or consortium)", None,
     "Apply to the Commission for Strategic Project recognition using the single template, and maintain the criteria that justified recognition. The Commission decides within 90 days of a complete application, extendable once by up to 90 days."),
    ("Art 8(1)", "medium", "project promoter", None,
     "Submit a progress report to the Commission every two years after Strategic Project recognition."),
    ("Art 9(1)", "high", "Member State", date(2025, 2, 24),
     "Establish or designate a single point of contact for critical raw material permitting by 24 February 2025."),
    ("Art 11(1)", "high", "Member State (permitting authority)", None,
     "Complete the Strategic Project permit-granting process within 27 months for extraction and 15 months for processing or recycling, extendable by a maximum of 6 or 3 months in exceptional cases."),
    ("Art 19(1)", "medium", "Member State", date(2025, 5, 24),
     "Draw up a national general-exploration programme for critical raw materials by 24 May 2025."),
    ("Art 20", "high", "European Commission (with Member States)", None,
     "Monitor supply-risk parameters and ensure a stress test of each strategic raw material supply chain at least every 3 years."),
    ("Art 21(2)", "medium", "Member State", None,
     "Identify and monitor the key market operators along the critical raw materials value chain established on its territory."),
    ("Art 22(1)", "medium", "Member State", None,
     "Report annually to the Commission on the state of strategic stocks of strategic raw materials held on its territory. Holding or releasing stocks is not mandatory."),
    ("Art 24(2)", "high", "large company (>500 employees, >150m euros turnover)", None,
     "Carry out a supply-chain risk assessment of the strategic raw materials used to manufacture listed strategic technologies, at least every 3 years, and report the findings to the board or equivalent."),
    ("Art 25(1)", "medium", "European Commission", None,
     "Set up and operate a demand-aggregation and joint-purchasing system for strategic raw materials open to interested Union undertakings."),
    ("Art 26(1)", "high", "Member State", None,
     "Adopt and implement national programmes to increase the circularity of critical raw materials within 2 years of the relevant implementing act."),
    ("Art 27(1)", "medium", "operator of an extractive waste facility", date(2026, 11, 24),
     "Submit a preliminary economic assessment study on the recovery of critical raw materials from extractive waste, by 24 November 2026."),
    ("Art 27(4)", "medium", "Member State", None,
     "Establish and populate a database of closed extractive waste facilities with critical raw material recovery potential."),
    ("Art 28(1)", "high", "manufacturer / economic operator", None,
     "Label in-scope products (for example motor vehicles, wind generators, industrial robots, heat pumps) to disclose incorporated permanent magnets and their type."),
    ("Art 28(3)", "medium", "economic operator placing the product on the market", None,
     "Provide a data carrier giving access to permanent magnet composition, location and safe-removal information."),
    ("Art 29(1)", "medium", "economic operator", date(2027, 5, 24),
     "Disclose the recycled-content share of critical elements in permanent magnets exceeding 0.2 kg, by 24 May 2027."),
    ("Art 31(6)", "low", "person placing the critical raw material on the market", None,
     "Make available an environmental footprint declaration for a critical raw material once Commission calculation rules exist for it."),
    ("Art 32", "medium", "Member State", None,
     "Do not restrict, prohibit or impede the market access of compliant permanent-magnet products or critical raw materials on recycling or footprint-information grounds."),
]

db = SessionLocal()
try:
    from sqlalchemy import text as _t
    n = db.execute(_t("DELETE FROM law_requirements WHERE law_id=:l AND cluster_id=:c"),
                   {"l": CRMA_LAW_ID, "c": CRMA_CLUSTER_ID}).rowcount
    if n:
        print(f"[purge] removed {n} prior CRMA requirements")
    for art, crit, ent, dl, txt in R:
        db.add(LawRequirement(
            law_id=CRMA_LAW_ID, cluster_id=CRMA_CLUSTER_ID,
            article=art[:50], requirement_text=txt, deadline=dl,
            criticality=crit, applicable_entity=ent[:100],
            extra_metadata={"source": "canon_curated_seed", "seeded_at": "2026-08-12"},
        ))
    db.commit()
    print(f"[seeded] {len(R)} CRMA requirements into law_requirements")
finally:
    db.close()
