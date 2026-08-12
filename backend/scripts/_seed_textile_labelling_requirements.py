"""Seed the headline obligations of Regulation (EU) No 1007/2011 (textile fibre
names and fibre-composition labelling) into law_requirements.

Part of the 13-act textile/ESPR product-architecture series -> shared hub
cluster 65 ("EU Digital Product Passport regime"). LAW_ID 14974.
  SELECT id, celex FROM eu_laws WHERE celex='32011R1007'; -> 14974
Curated from a sequential read (28 Articles, 4 Chapters, Annexes I-X).
Brubru canon, 13 Aug 2026.
"""
import sys
from datetime import date
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root)); sys.path.insert(0, str(project_root / "backend"))
from dotenv import load_dotenv; load_dotenv(project_root / ".env")
from core.database import SessionLocal
from models.eu_law import LawRequirement

LAW_ID, HUB = 14974, 65
APP = date(2012, 5, 8)
R = [
 ("Art 4 / Art 14", "critical", "economic operator placing on the market", APP,
  "Make available on the market only textile products that are labelled or marked to indicate their fibre composition in accordance with this Regulation."),
 ("Art 5 / Annex I", "critical", "economic operator", APP,
  "Use only the textile fibre names listed in Annex I to describe fibre content. Names not in Annex I may not be used unless added by the Commission under Article 6."),
 ("Art 9", "high", "economic operator", APP,
  "For a multi-fibre product, state the name and percentage by weight of all constituent fibres in descending order. Give the full composition; do not omit fibres above the applicable thresholds."),
 ("Art 7", "high", "economic operator", APP,
  "Use the terms '100 %', 'pure' or 'all' only for a textile product composed exclusively of one and the same fibre."),
 ("Art 12", "high", "economic operator", APP,
  "Indicate the presence of non-textile parts of animal origin with the phrase 'Contains non-textile parts of animal origin' on the label or marking, and ensure the labelling is not misleading."),
 ("Art 14 / Art 16", "high", "economic operator", APP,
  "Ensure the label or marking is durable, easily legible, visible and accessible, affixed so it stays with the product when made available on the market."),
 ("Art 16(3)", "medium", "economic operator", APP,
  "Provide the labelling and marking in the official language or languages of the Member State in which the textile product is made available to the consumer."),
 ("Art 15 / Art 16", "high", "importer / distributor", APP,
  "Importers and distributors must ensure the products they place on or make available on the market carry the required label or marking; a distributor is treated as the responsible operator where it markets under its own name."),
 ("Art 6 / Annex II", "medium", "manufacturer applying for a new fibre name", None,
  "To request a new textile fibre name in Annex I, submit to the Commission a technical file meeting the minimum requirements of Annex II."),
 ("Art 19 / Annexes VII-IX", "medium", "economic operator / test laboratory", APP,
  "Apply the extraneous-fibre tolerances and the agreed allowances set out in Article 19 and Annexes VII to IX when determining fibre content by analysis."),
 ("Art 20", "medium", "manufacturer (exceptional cases)", None,
  "Where a manufacturing process requires tolerances higher than the standard ones, obtain prior authorisation from the Commission before placing the product on the market, providing evidence of the exceptional circumstances."),
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
                              extra_metadata={"source": "canon_curated_seed", "seeded_at": "2026-08-13"}))
    db.commit()
    print(f"[seeded] {len(R)} textile fibre labelling requirements into hub {HUB}")
finally:
    db.close()
