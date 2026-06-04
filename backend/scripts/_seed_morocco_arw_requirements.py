"""Seed the canonical headline obligations of Commission Implementing Regulation (EU)
2025/500 (Morocco aluminium road wheels countervailing duties) into law_requirements.
Pre-curated from a full top-to-bottom read (data/canon/2025-500_morocco_aluminium_wheels.analysis.md).
article and applicable_entity are VARCHAR(50).

ids verified live against prod Supabase on 26 May 2026:
  eu_laws id for 32025R0500 -> 10893
  law_clusters 'Morocco Aluminium Road Wheels...' -> 28
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root)); sys.path.insert(0, str(project_root / "backend"))
from dotenv import load_dotenv
load_dotenv(project_root / ".env")
from backend.core.database import SessionLocal
from backend.models.eu_law import LawRequirement

LAW_ID = 10893
CLUSTER_ID = 28

REQUIREMENTS = [
    {"article": "Article 1(1) (product + duty)",
     "requirement_text": "A definitive countervailing duty is imposed on imports of certain aluminium road wheels of motor vehicles of HS headings 8701 to 8705, whether or not with accessories and whether or not fitted with tyres, currently falling under CN codes ex 8708 70 10 and ex 8708 70 50 (TARIC 8708701015, 8708701050, 8708705015, 8708705050) and originating in Morocco.",
     "criticality": "critical", "applicable_entity": "EU importers of Moroccan ARW"},
    {"article": "Article 1(2) (DMA rate)",
     "requirement_text": "The definitive countervailing duty on the net, free-at-Union-frontier price before duty for aluminium road wheels produced by Dika Morocco Africa S.A. is 31.4% (TARIC additional code C897).",
     "criticality": "critical", "applicable_entity": "Dika Morocco Africa S.A."},
    {"article": "Article 1(2) (Hands 8 + residual)",
     "requirement_text": "The definitive countervailing duty is 5.6% for Hands 8 S.A. (TARIC additional code C873) and 5.6% for all other imports originating in Morocco (TARIC additional code C999).",
     "criticality": "critical", "applicable_entity": "Hands 8 and all other Morocco"},
    {"article": "Relationship to anti-dumping duties",
     "requirement_text": "These countervailing duties apply in addition to the definitive anti-dumping duties of 9.0% to 17.5% already imposed on the same product from Morocco by Commission Implementing Regulation (EU) 2023/99, subject to the rule against double-counting export subsidies.",
     "criticality": "important", "applicable_entity": "EU importers of Moroccan ARW"},
    {"article": "Article 1(3) (invoice condition)",
     "requirement_text": "Application of the individual (company-specific) duty rates is conditional on presentation to customs of a valid commercial invoice bearing a dated and signed declaration by a named official certifying the manufacturer and TARIC additional code; otherwise the all-other-imports rate applies.",
     "criticality": "important", "applicable_entity": "exporting producers / importers"},
    {"article": "Cross-border subsidy attribution",
     "requirement_text": "Chinese preferential financing under the Belt and Road Initiative, channelled through CITIC Dicastal into its Moroccan subsidiary, is attributed to the Government of Morocco as the country of export, applying the doctrine affirmed by the Court of Justice on 28 November 2024 in the Hengshi/Jushi Egypt cases (C-269/23 P and C-272/23 P).",
     "criticality": "important", "applicable_entity": "Moroccan exporting producers"},
    {"article": "Subsidy schemes (DMA)",
     "requirement_text": "DMA's countervailed subsidies (overall 31.45%) include a preferential price of inputs (15.65%), de facto loans linked to capital goods (5.44%) and to the provision of inputs (2.03%), capitalised loans and payables, loans from related Chinese entities, a grant, and Moroccan import-duty, corporate-income-tax and professional-tax exemptions.",
     "criticality": "informational", "applicable_entity": "Dika Morocco Africa S.A."},
    {"article": "Subsidy schemes (Hands 8)",
     "requirement_text": "Hands 8's countervailed subsidies (overall 5.60%) include a grant (1.57%) and Moroccan import-duty, corporate-income-tax and professional-tax exemptions, plus a preferential-financing element.",
     "criticality": "informational", "applicable_entity": "Hands 8 S.A."},
    {"article": "Level of measures (no lesser duty)",
     "requirement_text": "Under Article 15(1) of the basic Regulation the duty may not exceed the countervailable subsidies; the lesser-duty rule does not apply in anti-subsidy investigations unless the full amount is clearly not in the Union interest, so the duty is set at the full subsidy amount.",
     "criticality": "important", "applicable_entity": "exporting producers / importers"},
    {"article": "Injury and causation finding",
     "requirement_text": "The Commission found material injury to the Union industry (profitability falling from 1% in 2020 to minus 3% in the investigation period, market share falling from 71% to 65%) caused by surging subsidised Moroccan imports (volume index 100 to 675; market share 2% to 9%).",
     "criticality": "informational", "applicable_entity": "Union ARW industry"},
    {"article": "Association Agreement objection",
     "requirement_text": "The Commission rejected Morocco's argument that countervailing duties are barred by Articles 8 and 9 of the EU-Morocco Euro-Mediterranean Association Agreement, relying on Article 36, which makes the GATT Article VI rules (and thus the WTO ASCM and the basic Regulation) the applicable disciplines for trade-distorting subsidies.",
     "criticality": "informational", "applicable_entity": "Government of Morocco"},
    {"article": "Article 2 (entry into force)",
     "requirement_text": "The Regulation enters into force on the day following its publication in the Official Journal of the European Union; unless otherwise specified, the provisions in force concerning customs duties apply.",
     "criticality": "informational", "applicable_entity": "EU importers / customs authorities"},
]


def main():
    db = SessionLocal()
    try:
        if db.query(LawRequirement).filter(LawRequirement.law_id == LAW_ID).count():
            print("[INFO] requirements already exist. Skipping."); return
        bad = [r["article"] for r in REQUIREMENTS if len(r["article"]) > 50] + \
              [r["applicable_entity"] for r in REQUIREMENTS if len(r["applicable_entity"]) > 50]
        if bad:
            print("ABORT: >50 chars:", bad); sys.exit(1)
        for r in REQUIREMENTS:
            db.add(LawRequirement(law_id=LAW_ID, cluster_id=CLUSTER_ID,
                   article=r["article"], requirement_text=r["requirement_text"],
                   criticality=r["criticality"], applicable_entity=r["applicable_entity"]))
        db.commit()
        print(f"[OK] seeded {len(REQUIREMENTS)} requirements for law_id={LAW_ID}, cluster_id={CLUSTER_ID}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
