"""Seed the headline obligations of Regulation (EU) 2026/405 (the Detergents
Regulation) into law_requirements. DPP-regime act -> hub cluster 65.
  SELECT id, celex FROM eu_laws WHERE celex='32026R0405'; -> 28685
Curated from a sequential read (37 Articles, 8 Chapters) - Brubru canon, 12 Aug 2026.
"""
import sys
from datetime import date
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root)); sys.path.insert(0, str(project_root / "backend"))
from dotenv import load_dotenv; load_dotenv(project_root / ".env")
from core.database import SessionLocal
from models.eu_law import LawRequirement

LAW_ID, HUB = 28685, 65
APP = date(2029, 9, 23)
R = [
 ("Art 3(1)","critical","all economic operators",APP,"Make available on the market only detergents or surfactants that comply with this Regulation."),
 ("Art 4(1)","critical","manufacturer",APP,"Ensure surfactants, alone or contained in detergents, meet the Annex I Part A ultimate aerobic biodegradability criteria (60 percent in 28 days by four test methods, or 70 percent by two)."),
 ("Art 5","high","manufacturer",APP,"Ensure a detergent containing micro-organisms meets the Annex II identification, safety and risk-assessment requirements, including the minimum plate counts and shelf life."),
 ("Art 6","high","manufacturer",APP,"Comply with the Annex III phosphorus and phosphate content limits for the listed detergent categories (0.5 g per dose consumer laundry, 0.3 g per dose consumer dishwasher)."),
 ("Art 7(2)","high","manufacturer",APP,"Do not place on the market a detergent or surfactant whose final formulation or ingredients were animal-tested to meet this Regulation."),
 ("Art 8(2)","critical","manufacturer",APP,"Draw up technical documentation and carry out the Module A self-declared conformity assessment procedure before placing on the market. There is no CE marking and no notified body for detergents."),
 ("Art 8(2)","critical","manufacturer",APP,"Create the digital product passport and upload the identifiers to the registry before placing the product on the market."),
 ("Art 8(3)","high","manufacturer",None,"Keep the technical documentation and the digital product passport for 10 years after placing on the market."),
 ("Art 8(6)","medium","manufacturer",None,"Provide and keep updated the ingredients data sheet to the Member States' appointed bodies before placing certain mixtures on the market."),
 ("Art 9(3)","medium","authorised representative",None,"Perform tasks under a written mandate, keeping the technical documentation and the digital product passport available for 10 years."),
 ("Art 10(2)","high","importer",APP,"Verify the conformity assessment, technical documentation, digital product passport, data carrier and registry upload before placing a product on the market."),
 ("Art 11(2)","medium","distributor",APP,"Verify the accompanying documents, the label and, where used, the digital label and data carrier before making a product available."),
 ("Art 12","medium","economic operator offering refill",None,"Apply risk-mitigation measures at refill stations, including preventing unsupervised child access and training staff."),
 ("Art 15","medium","all economic operators",None,"Identify the upstream and downstream supply-chain operators on request, for 10 years."),
 ("Art 17","high","manufacturer / importer",APP,"Accompany products made available in individual packaging or through refill with a label meeting the Annex V requirements."),
 ("Art 19(1)","medium","economic operator providing a digital label",None,"Meet the digital-label accessibility, searchability, non-tracking and 10-year-availability requirements where a digital label is used."),
 ("Art 21","critical","manufacturer",APP,"Create a digital product passport meeting the Annex VI content requirements before placing a detergent or end-user surfactant on the market."),
 ("Art 24(1)","high","economic operator placing the product on the market",APP,"Upload the unique product identifier and the unique operator identifier to the digital product passport registry before placing on the market."),
 ("Art 25(2)","medium","importer / declarant",None,"Provide the unique registration identifier to customs authorities when placing an imported product under the free-circulation procedure."),
 ("Art 33","medium","Member State",None,"Lay down effective, proportionate and dissuasive penalties for infringements and notify the Commission of the rules."),
]
db = SessionLocal()
try:
    from sqlalchemy import text as _t
    n = db.execute(_t("DELETE FROM law_requirements WHERE law_id=:l AND cluster_id=:c"), {"l":LAW_ID,"c":HUB}).rowcount
    if n: print(f"[purge] {n}")
    for art,crit,ent,dl,txt in R:
        db.add(LawRequirement(law_id=LAW_ID, cluster_id=HUB, article=art[:50], requirement_text=txt,
                              deadline=dl, criticality=crit, applicable_entity=ent[:100],
                              extra_metadata={"source":"canon_curated_seed","seeded_at":"2026-08-12"}))
    db.commit(); print(f"[seeded] {len(R)} Detergents requirements into hub {HUB}")
finally:
    db.close()
