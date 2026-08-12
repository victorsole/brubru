"""Seed the headline obligations of Commission Delegated Regulation (EU) 2026/296
(the ESPR unsold-goods destruction-BAN derogations) into law_requirements.

Part of the 13-act ESPR product-architecture series -> shared hub cluster 65
("EU Digital Product Passport regime"). LAW_ID 28678.
  SELECT id, celex FROM eu_laws WHERE celex='32026R0296'; -> 28678
Curated from a sequential read (6 Articles). The BAN itself is ESPR Art 25(1);
this act sets the derogations and the documentation regime. Brubru canon, 13 Aug 2026.
"""
import sys
from datetime import date
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root)); sys.path.insert(0, str(project_root / "backend"))
from dotenv import load_dotenv; load_dotenv(project_root / ".env")
from core.database import SessionLocal
from models.eu_law import LawRequirement

LAW_ID, HUB = 28678, 65
APP = date(2026, 7, 19)
R = [
 ("ESPR Art 25(1)", "critical", "economic operator", APP,
  "From 19 July 2026, do not destroy unsold consumer products listed in ESPR Annex VII (currently apparel and clothing accessories, and footwear) unless one of the derogations in Article 2 applies. The prohibition is set by the ESPR; this Regulation defines the exceptions."),
 ("Art 2 / ESPR Art 2(34)", "high", "economic operator", APP,
  "Treat destruction as a last resort: before destroying, consider remanufacturing, refurbishing, donating or preparing the product for reuse. Destruction is only lawful where a specific Article 2 derogation applies and its documentation can be produced."),
 ("Art 2(a)-(g)", "high", "economic operator", APP,
  "Destruction is permitted where the product is dangerous under Regulation (EU) 2023/988 (a); non-compliant with law and destruction is required or proportionate (b); infringes IP by a final decision, ADR, notification or substantiated investigation (c); is under an expired IP licence or contractual restriction (d); cannot have IP-protected or inappropriate labels/logos/design removed (e); is damaged, deteriorated or contaminated and not feasibly repairable (f); or is defective by design or manufacture and not technically repairable (g)."),
 ("Art 2(h)", "high", "economic operator", APP,
  "Only where none of points (a) to (g) apply, a product may be destroyed after it was offered for donation, either directly to at least three suitable social economy entities in the Union or on an easily accessible website page for at least eight weeks, and was not accepted."),
 ("Art 2(i)-(j)", "medium", "social economy entity or operator", APP,
  "A donated product for which a social economy entity in the Union could find no recipient (i), or a product made available after preparation for reuse by a waste treatment operator for which no recipient could be found (j), may be destroyed."),
 ("Recital 3 / WFD Art 4", "medium", "economic operator", APP,
  "Where a derogation applies and the product is destroyed, follow the waste hierarchy of Article 4 of Directive 2008/98/EC, prioritising recycling over other recovery, including energy recovery, and over disposal."),
 ("Art 3", "high", "economic operator", None,
  "Keep, for five years after destruction under a derogation, the documentation proving that derogation, and provide it to competent authorities in electronic form within 30 days of a request. Each derogation ground has its own required proof; documentation may be prepared collectively where products share the same circumstances."),
 ("Art 4", "medium", "economic operator", APP,
  "Provide a statement on the applicable derogation to the waste treatment operator to which the unsold consumer products are delivered, to support sorting, reuse and recycling."),
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
    print(f"[seeded] {len(R)} unsold-goods destruction-ban requirements into hub {HUB}")
finally:
    db.close()
