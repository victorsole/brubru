"""Add PPWR (32025R0040) and WFD-textiles (32025L1892) to the shared DPP hub
cluster 65, so the hub holds all 13 acts of the DPP legal-architecture series.

These two acts already live in legitimate topical clusters that must NOT be
emptied:
  - PPWR       -> cluster 57 "PPWR - Packaging and Packaging Waste Regulation"
  - WFD-textiles -> cluster 58 "Textiles: EPR, Ecodesign and DPP (DPP-TEX)" (Terraqui
                    client cluster) + cluster 62 "Food Waste Reduction Targets"
The other DPP-series acts (ESPR, DPP registry, unsold disclosure/ban) already
sit in BOTH their topical cluster (58) AND the hub (65): multi-cluster
membership is the established pattern. So we COPY each act's curated
requirement rows into 65, we do not move them.

  PPWR         law_id 23636: copy its 22 rows from cluster 57.
  WFD-textiles law_id 15039: copy its 20 DPP/EPR rows from cluster 58 (leave the
                             3 food-waste rows in cluster 62 alone).

Idempotent: deletes any existing rows for these two law_ids in cluster 65 first.
Brubru canon, 13 Aug 2026.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root)); sys.path.insert(0, str(project_root / "backend"))
from dotenv import load_dotenv; load_dotenv(project_root / ".env")
from core.database import SessionLocal
from models.eu_law import LawRequirement
from sqlalchemy import text as _t

HUB = 65
COPY = [
    (23636, 57),   # PPWR: copy rows from its packaging cluster
    (15039, 58),   # WFD-textiles: copy rows from the DPP-TEX cluster (not the food-waste one)
]

db = SessionLocal()
try:
    for law_id, src_cluster in COPY:
        deleted = db.execute(
            _t("DELETE FROM law_requirements WHERE law_id=:l AND cluster_id=:hub"),
            {"l": law_id, "hub": HUB}).rowcount
        if deleted:
            print(f"[purge] law {law_id}: removed {deleted} prior rows from hub {HUB}")
        rows = db.execute(_t(
            "SELECT article, requirement_text, deadline, criticality, applicable_entity, extra_metadata "
            "FROM law_requirements WHERE law_id=:l AND cluster_id=:c ORDER BY id"),
            {"l": law_id, "c": src_cluster}).fetchall()
        for art, txt, dl, crit, ent, meta in rows:
            m = dict(meta) if isinstance(meta, dict) else {}
            m.update({"copied_from_cluster": src_cluster, "hub_seeded_at": "2026-08-13"})
            db.add(LawRequirement(law_id=law_id, cluster_id=HUB, article=(art or "")[:50],
                                  requirement_text=txt, deadline=dl, criticality=crit,
                                  applicable_entity=(ent or "")[:100], extra_metadata=m))
        print(f"[copied] law {law_id}: {len(rows)} rows from cluster {src_cluster} into hub {HUB}")
    db.commit()
    # verify
    n_laws = db.execute(_t("SELECT count(distinct law_id) FROM law_requirements WHERE cluster_id=:h"),
                        {"h": HUB}).scalar()
    n_reqs = db.execute(_t("SELECT count(*) FROM law_requirements WHERE cluster_id=:h"),
                        {"h": HUB}).scalar()
    print(f"[hub {HUB}] now {n_reqs} requirements across {n_laws} acts")
finally:
    db.close()
