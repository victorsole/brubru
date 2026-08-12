"""Seed the headline obligations of Commission Implementing Regulation (EU) 2026/2
(the ESPR unsold-goods DISCLOSURE format) into law_requirements.

Part of the 13-act ESPR product-architecture series -> shared hub cluster 65
("EU Digital Product Passport regime"). LAW_ID 28677.
  SELECT id, celex FROM eu_laws WHERE celex='32026R0002'; -> 28677
Curated from a sequential read (7 Articles + Annexes I to III). Brubru canon, 12 Aug 2026.
"""
import sys
from datetime import date
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root)); sys.path.insert(0, str(project_root / "backend"))
from dotenv import load_dotenv; load_dotenv(project_root / ".env")
from core.database import SessionLocal
from models.eu_law import LawRequirement

LAW_ID, HUB = 28677, 65
APP = date(2027, 3, 2)
R = [
 ("ESPR Art 24(1) / Art 1", "critical", "large enterprise", APP,
  "Disclose, annually and within 12 months of the end of each financial year, the information on unsold consumer products discarded during that financial year. Applies to large enterprises now; micro and small enterprises are exempt."),
 ("ESPR Art 24(1)", "high", "medium-sized enterprise", date(2030, 7, 19),
  "From 19 July 2030, medium-sized enterprises that discard unsold consumer products, or have them discarded on their behalf, become subject to the same annual disclosure obligation."),
 ("Art 2(1) / Annex I", "critical", "economic operator subject to disclosure", APP,
  "Present the disclosure in the exact visual format and content set out in Annex I: number of units and total weight discarded per product category, reasons for discarding, applicable derogations, the proportion delivered to each waste treatment operation, and the measures taken and planned to prevent destruction."),
 ("Annex I", "high", "economic operator subject to disclosure", APP,
  "Report the split across waste treatment operations (preparing for reuse, recycling, other recovery including energy recovery, disposal, and unknown). Destruction is the sum of recycling, other recovery and disposal; preparing for reuse is not destruction."),
 ("Art 2(2)", "medium", "economic operator publishing CSRD reporting", APP,
  "A company publishing sustainability reporting under Article 19a or 29a of Directive 2013/34/EU that includes the Annex I information may, instead of disclosing on its website directly, provide a website link to that report clearly indicating where the unsold-goods information appears."),
 ("Art 3 / Annex II", "high", "economic operator subject to disclosure", APP,
  "Delimit product categories using the Combined Nomenclature: the first two digits of the CN code generally, but the categories listed in Annex II (apparel, textiles, leather and fur goods, electronics, appliances, batteries, furniture, toys, sanitary articles and others) at the four-digit CN level."),
 ("Art 4", "high", "economic operator subject to disclosure", None,
  "Keep the information and documentation needed to demonstrate the delivery and reception of discarded unsold consumer products, including waste-treatment statements, for five years after the disclosure."),
 ("Art 5 / Annex III", "medium", "competent national authority", None,
  "Verify compliance on a risk-based approach (no disclosure or unusually low numbers, past non-compliance, high percentage of unknown waste treatment, size of operations, other intelligence); treat a disclosed figure within 10 percent of the documented figure as compliant, and inform other affected Member States of cross-border non-compliance."),
 ("Note: donations", "medium", "economic operator", None,
  "Donated consumer products are not covered by the disclosure obligation, because donation is not discarding. Only products discarded as waste for a waste treatment operation are in scope."),
]
db = SessionLocal()
try:
    from sqlalchemy import text as _t
    n = db.execute(_t("DELETE FROM law_requirements WHERE law_id=:l AND cluster_id=:c"),
                   {"l": LAW_ID, "c": HUB}).rowcount
    if n:
        print(f"[purge] {n}")
    for art, crit, ent, dl, txt in R:
        db.add(LawRequirement(law_id=LAW_ID, cluster_id=HUB, article=art[:50],
                              requirement_text=txt, deadline=dl, criticality=crit,
                              applicable_entity=ent[:100],
                              extra_metadata={"source": "canon_curated_seed", "seeded_at": "2026-08-12"}))
    db.commit()
    print(f"[seeded] {len(R)} unsold-goods disclosure requirements into hub {HUB}")
finally:
    db.close()
