"""Seed the canonical headline obligations of Commission Implementing Regulation (EU)
2021/2011 (optical fibre cables from China, anti-dumping duties) into law_requirements.
Pre-curated from a full top-to-bottom read (data/canon/2021-2011_optical_fibre_cables.analysis.md).
article and applicable_entity are VARCHAR(50).

ids verified live against prod Supabase on 26 May 2026:
  eu_laws id for 32021R2011 -> 15118
  law_clusters 'Optical Fibre Cables...' -> 30
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root)); sys.path.insert(0, str(project_root / "backend"))
from dotenv import load_dotenv
load_dotenv(project_root / ".env")
from backend.core.database import SessionLocal
from backend.models.eu_law import LawRequirement

LAW_ID = 15118
CLUSTER_ID = 30

REQUIREMENTS = [
    {"article": "Article 1(1) (product + duty)",
     "requirement_text": "A definitive anti-dumping duty is imposed on imports of single-mode optical fibre cables, made up of one or more individually sheathed fibres with protective casing, whether or not containing electric conductors, currently falling under CN code ex 8544 70 00 (TARIC 8544700010) and originating in China. Connectorised cables and submarine cables are excluded.",
     "criticality": "critical", "applicable_entity": "EU importers of Chinese OFC"},
    {"article": "Article 1(2) (FTT + ZTT rates)",
     "requirement_text": "The definitive anti-dumping duty is 44.0% for the FTT group (FiberHome Telecommunication Technologies and related companies, TARIC additional code C696) and 19.7% for the ZTT group (Jiangsu Zhongtian Technology and related companies, TARIC additional code C697).",
     "criticality": "critical", "applicable_entity": "FTT group / ZTT group"},
    {"article": "Article 1(2) (cooperating + residual)",
     "requirement_text": "The duty is 31.2% for other cooperating companies listed in Annex I, and 44.0% for all other companies (TARIC additional code C999).",
     "criticality": "critical", "applicable_entity": "cooperating / all other companies"},
    {"article": "Article 2(6a) methodology",
     "requirement_text": "Because Chinese domestic prices and costs were found to be affected by significant distortions, the normal value was constructed under Article 2(6a) of the basic Regulation using undistorted costs from a representative country, Argentina.",
     "criticality": "informational", "applicable_entity": "Chinese exporting producers"},
    {"article": "Lesser-duty rule",
     "requirement_text": "The lesser-duty rule applies in anti-dumping: the duty is the lower of the dumping margin and the injury elimination level. The injury elimination levels (FTT 61.3%, ZTT 42.0%, other 52.7%, all 61.3%) were higher than the dumping margins, so the duties were set at the dumping margins.",
     "criticality": "important", "applicable_entity": "exporting producers / importers"},
    {"article": "Injury and causation finding",
     "requirement_text": "The Commission found material injury to the Union industry, with the sampled Chinese exporters undercutting Union prices by 30.0% and 33.2% (overall undercutting 31.5%), price depression and lost sales, and a causal link with the dumped imports.",
     "criticality": "informational", "applicable_entity": "Union OFC industry"},
    {"article": "Article 1(3) (invoice condition)",
     "requirement_text": "Application of the individual (company-specific) duty rates is conditional on presentation to customs of a valid commercial invoice bearing a dated and signed declaration by a named official identifying the manufacturer and TARIC additional code; otherwise the all-other-companies rate applies.",
     "criticality": "important", "applicable_entity": "exporting producers / importers"},
    {"article": "Article 1(5) (length declaration)",
     "requirement_text": "The customs declaration must indicate the length in kilometres of the product, provided this is compatible with the Combined Nomenclature.",
     "criticality": "informational", "applicable_entity": "EU importers / customs"},
    {"article": "Article 2 (new-exporter review)",
     "requirement_text": "A genuine new exporting producer from China that did not export during the investigation period, is not related to a producer subject to the measures, and has exported or contracted to export to the Union, may be added to Annex I and subject to the 31.2% cooperating rate.",
     "criticality": "informational", "applicable_entity": "new Chinese exporting producers"},
    {"article": "Article 3 (registration)",
     "requirement_text": "Customs authorities are directed to discontinue the registration of imports that had been established by Commission Implementing Regulation (EU) 2021/548.",
     "criticality": "informational", "applicable_entity": "customs authorities"},
    {"article": "Union interest + parallel case",
     "requirement_text": "The Commission confirmed under Article 21 that measures were in the Union interest. A separate anti-subsidy (countervailing) investigation was initiated on the same product on 21 December 2020 and pursued in parallel.",
     "criticality": "informational", "applicable_entity": "Union industry / importers"},
    {"article": "Article 4 (entry into force)",
     "requirement_text": "The Regulation enters into force on the day following its publication in the Official Journal of the European Union; unless otherwise specified, the provisions in force concerning customs duties apply.",
     "criticality": "informational", "applicable_entity": "EU importers / customs"},
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
