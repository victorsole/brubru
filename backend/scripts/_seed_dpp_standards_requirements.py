"""Seed the DPP harmonised-standards conformity route of Commission Implementing
Decision (EU) 2026/1736 into law_requirements.

This Decision imposes no obligations, deadlines or penalties: it publishes the
references of six harmonised EN standards for the digital product passport and,
through ESPR Article 41(2), switches on a PRESUMPTION OF CONFORMITY. What we seed
is therefore the available compliance route, not a mandate, framed for EU Law
Comply as the standards fast lane through ESPR Articles 10 and 11.

DPP-regime act -> shared hub cluster 65 ("EU Digital Product Passport regime").
  SELECT id, celex FROM eu_laws WHERE celex='32026D1736'; -> 28686
Brubru canon, 12 Aug 2026.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root)); sys.path.insert(0, str(project_root / "backend"))
from dotenv import load_dotenv; load_dotenv(project_root / ".env")
from core.database import SessionLocal
from models.eu_law import LawRequirement

LAW_ID, HUB = 28686, 65
R = [
 ("Art 1 / EN 18216-18223:2026", "medium", "economic operator building a DPP", None,
  "Optional conformity route: build the digital product passport to the six harmonised standards published by this Decision (EN 18216, 18219, 18220, 18221, 18222 and 18223:2026) to obtain a presumption of conformity with the requirements in Articles 10 and 11 of the ESPR (Regulation (EU) 2024/1781) covered by those standards. Conformity from the OJ publication date, 15 July 2026."),
 ("EN 18219 / EN 18220:2026", "medium", "economic operator building a DPP", None,
  "Where the standards route is used, apply EN 18219:2026 (unique identifiers) for the passport, product and operator identifiers and EN 18220:2026 (data carriers) for the on-product carrier that links a product to its passport."),
 ("EN 18216 / EN 18221 / EN 18222 / EN 18223:2026", "medium", "economic operator building a DPP", None,
  "Where the standards route is used, apply EN 18216:2026 (data exchange protocols), EN 18221:2026 (data storage, archiving and persistence), EN 18222:2026 (APIs for lifecycle management and searchability) and EN 18223:2026 (system interoperability) so the passport can exchange, store, be served through APIs and interoperate across sectors and Member States."),
 ("ESPR Art 41(2)", "high", "economic operator building a DPP", None,
  "The presumption of conformity is limited to the requirements the standard actually covers: it does not certify compliance with any ESPR or sectoral requirement outside the scope of the six standards, and it is not proof of compliance with the substantive product law. The standards route lowers the evidentiary burden, it does not replace the underlying obligations."),
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
    print(f"[seeded] {len(R)} DPP standards conformity-route items into hub {HUB}")
finally:
    db.close()
