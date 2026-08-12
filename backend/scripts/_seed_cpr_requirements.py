"""Seed the canonical headline obligations of Regulation (EU) 2024/3110 (the
revised Construction Products Regulation, CPR) into law_requirements.

Pre-curated from a sequential read of the Regulation (Articles 1-96, 15 Chapters)
- Brubru canon project, 12 August 2026. Annex-only figures flagged by the reader
are not asserted here.

NOTE (12 Aug 2026): the Digital Product Passport regime acts share ONE EU Law
Comply hub cluster (id 65, "EU Digital Product Passport regime (ESPR + product
laws)"), not a per-law cluster. CPR's requirements seed into cluster 65.
  SELECT id, celex FROM eu_laws WHERE celex='32024R3110'; -> 18866
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

CPR_LAW_ID = 18866
DPP_HUB_CLUSTER_ID = 65

R = [
    ("Art 4(2)", "medium", "European Commission", date(2026, 1, 8),
     "Publish the first working plan for harmonised technical specifications by 8 January 2026 and renew it at least every 3 years."),
    ("Art 13", "critical", "manufacturer", date(2026, 1, 8),
     "Draw up a declaration of performance and conformity (DoPC) before placing on the market a product covered by a harmonised technical specification."),
    ("Art 15(3)", "high", "manufacturer", None,
     "Cover the Annex II predetermined environmental essential characteristics in the declaration of performance and conformity on the phased timetable (2026, 2030 and 2032)."),
    ("Art 16", "high", "manufacturer", date(2026, 1, 8),
     "Supply the declaration of performance and conformity electronically, or make it available on an unamendable, monitored, freely accessible website in the required languages."),
    ("Art 17-18", "critical", "manufacturer / economic operator affixing the marking", date(2026, 1, 8),
     "Affix the CE marking, in the prescribed format, only to products for which a declaration of performance and conformity has been drawn up."),
    ("Art 20(4)", "high", "all economic operators", None,
     "Keep all documents and information at the disposal of competent authorities for 10 years after the product is supplied."),
    ("Art 22(3)", "high", "manufacturer", None,
     "Draw up technical documentation and maintain procedures ensuring series-produced products keep their declared performance."),
    ("Art 22(7)", "high", "manufacturer", None,
     "Make a digital product passport available through the construction DPP system once the applicable timeline under Article 80 starts running."),
    ("Art 22(8)", "medium", "manufacturer", None,
     "Ensure specified spare parts remain available for 10 years after the last product of the type is placed on the market, where a delegated act so requires."),
    ("Art 22(11)-(12)", "high", "manufacturer", None,
     "Take corrective action and, where a product presents a risk, inform downstream operators and authorities within 3 working days."),
    ("Art 23(2)", "medium", "authorised representative", None,
     "Perform the mandated tasks, at minimum keeping the declaration of performance and conformity and technical documentation available and cooperating on risk."),
    ("Art 24", "high", "importer", date(2026, 1, 8),
     "Verify CE marking, declaration availability and manufacturer compliance, and ensure product information is in the required language, before placing a product on the market."),
    ("Art 25(2)", "medium", "distributor", date(2026, 1, 8),
     "Verify CE marking, declaration availability and product information before making a product available on the market."),
    ("Art 26", "high", "importer / distributor (in defined cases)", None,
     "Assume full manufacturer obligations where placing a product under own name or brand, materially modifying it, or changing its declared use."),
    ("Art 27", "medium", "fulfilment service provider", None,
     "Ensure labelling and required documents accompany the product, and that warehousing and dispatch conditions do not affect compliance."),
    ("Art 28", "high", "online marketplace", None,
     "Design the online interface to support economic operators' obligations, and act on market surveillance orders to remove non-compliant listings."),
    ("Art 39(3)", "medium", "Member State (designating authority)", None,
     "Monitor designated technical assessment bodies and impose corrective measures for non-compliance."),
    ("Art 46 / 55", "high", "notified body", None,
     "Meet independence, competence and impartiality requirements, and carry out the assigned assessment, verification and validation tasks."),
    ("Art 65(1)", "high", "market surveillance authority", None,
     "Evaluate suspected non-compliant products or manufacturers, and require corrective action, withdrawal or recall within a reasonable period."),
    ("Art 92", "medium", "Member State", date(2026, 12, 8),
     "Lay down effective, proportionate and dissuasive penalties for infringements, and notify the Commission by 8 December 2026."),
]

db = SessionLocal()
try:
    from sqlalchemy import text as _t
    n = db.execute(_t("DELETE FROM law_requirements WHERE law_id=:l AND cluster_id=:c"),
                   {"l": CPR_LAW_ID, "c": DPP_HUB_CLUSTER_ID}).rowcount
    if n:
        print(f"[purge] removed {n} prior CPR requirements")
    for art, crit, ent, dl, txt in R:
        db.add(LawRequirement(
            law_id=CPR_LAW_ID, cluster_id=DPP_HUB_CLUSTER_ID,
            article=art[:50], requirement_text=txt, deadline=dl,
            criticality=crit, applicable_entity=ent[:100],
            extra_metadata={"source": "canon_curated_seed", "seeded_at": "2026-08-12"},
        ))
    db.commit()
    print(f"[seeded] {len(R)} CPR requirements into hub cluster {DPP_HUB_CLUSTER_ID}")
finally:
    db.close()
