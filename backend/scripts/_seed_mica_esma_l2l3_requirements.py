"""Enrich the MiCA EU Law Comply cluster (id 27, law_id 28662) with the ESMA/EBA
Level 2 and Level 3 implementation layer: RTS, ITS, the white-paper iXBRL taxonomy,
record-keeping / order-book message specs, and the public registers.

Sourced from a full read of the 16 ESMA/EC MiCA source files (Dec 2025), incl. the
ESMA smooth-implementation statement ESMA75-1303207761-6284, the MiCA taxonomy 2025
package + reporting manual, the ISO 20022 order-book/record-keeping message specs, and
the five ESMA register CSVs (CASPS/ARTZZ/EMTWP/OTHER/NCASP).

Adds ONLY articles not already present for cluster 27 (the 16 Level-1 rows stay).
article + applicable_entity are VARCHAR(50). Idempotent: skips articles already seeded.
"""
import sys
from datetime import date
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root)); sys.path.insert(0, str(project_root / "backend"))
from dotenv import load_dotenv
load_dotenv(project_root / ".env")
from backend.core.database import SessionLocal
from backend.models.eu_law import LawRequirement

MICA_LAW_ID = 28662
MICA_CLUSTER_ID = 27
SRC = "ESMA statement ESMA75-1303207761-6284 + MiCA taxonomy 2025 + ISO20022 message specs + ESMA registers"

REQUIREMENTS = [
    {"article": "ITS 2024/2984 (white-paper iXBRL)",
     "requirement_text": "Crypto-asset white papers must be drawn up as a single XHTML file with Inline XBRL 1.1 tagging against the MiCA taxonomy, per Implementing Regulation (EU) 2024/2984 (applies 23 December 2025). Tables 2 (other crypto-assets), 3 (asset-referenced tokens) and 4 (e-money tokens) set the mandatory field lists. ESMA provides voluntary SCWP Excel generators (OTHR/ART/EMT variants) that emit compliant iXBRL.",
     "criticality": "critical", "applicable_entity": "white-paper preparers (ART/EMT/OTHR)",
     "deadline": date(2025, 12, 23), "level": "L2", "instrument": "Commission Implementing Regulation (EU) 2024/2984"},
    {"article": "MiCA taxonomy 2025 (iXBRL tagging)",
     "requirement_text": "White papers must validate against the MiCA White Paper XBRL taxonomy (namespace 2025-03-31), a closed taxonomy carrying 257 existence and 223 value assertions across Tables 2/3/4; any fact failing an assertion of severity ERROR blocks compliance. Each language version is a separate, identically tagged iXBRL file, with the reporting entity identified by LEI.",
     "criticality": "important", "applicable_entity": "white-paper preparers (ART/EMT/OTHR)",
     "level": "L2/L3", "instrument": "MiCA taxonomy 2025 + iXBRL Reporting Manual v1.0"},
    {"article": "RTS 2025/421 (WP classification)",
     "requirement_text": "Each white paper must carry machine-readable classification data per Delegated Regulation (EU) 2025/421, so the crypto-asset can be classified and identified (including by Digital Token Identifier) in the ESMA register.",
     "criticality": "important", "applicable_entity": "white-paper preparers",
     "level": "L2", "instrument": "Commission Delegated Regulation (EU) 2025/421"},
    {"article": "RTS 2025/1140 (record-keeping)",
     "requirement_text": "All CASPs must keep records of every crypto-asset service, activity, order and transaction and provide them to competent authorities in the standardised ISO 20022 JSON format (messages auth.116 order-keeping and auth.117 record-keeping), per Delegated Regulation (EU) 2025/1140. Transaction records are maintained from 30 June 2025; clients identified by LEI (ISO 17442), assets by DTI (ISO 24165).",
     "criticality": "critical", "applicable_entity": "CASP",
     "deadline": date(2025, 6, 30), "level": "L2", "instrument": "Commission Delegated Regulation (EU) 2025/1140"},
    {"article": "RTS 2025/416 (order-book records)",
     "requirement_text": "CASPs operating a trading platform must keep order-book records in JSON per the ISO 20022 message auth.118 (CryptoAssetOrderBookReport), per Delegated Regulation (EU) 2025/416. Competent authorities begin requesting the JSON format within six months of the 28 November 2025 message-specification publication.",
     "criticality": "critical", "applicable_entity": "CASP (trading platform)",
     "level": "L2", "instrument": "Commission Delegated Regulation (EU) 2025/416"},
    {"article": "RTS 2025/417 (trading transparency)",
     "requirement_text": "CASPs operating a trading platform must present pre- and post-trade transparency data in the manner prescribed by Delegated Regulation (EU) 2025/417.",
     "criticality": "important", "applicable_entity": "CASP (trading platform)",
     "level": "L2", "instrument": "Commission Delegated Regulation (EU) 2025/417"},
    {"article": "LEI + DTI identification (L2)",
     "requirement_text": "Legal-entity parties (reporting entity and clients) must be identified by Legal Entity Identifier (ISO 17442) and each crypto-asset by Digital Token Identifier (ISO 24165), sourced from the DTIF registry where no white paper is notified, across white papers, record-keeping (auth.117) and order-book (auth.118) reports.",
     "criticality": "important", "applicable_entity": "CASP / white-paper preparers",
     "level": "L2", "instrument": "RTS (EU) 2025/1140 Arts 14-15 + RTS (EU) 2025/421"},
    {"article": "RTS 2025/885 (market abuse + STOR)",
     "requirement_text": "Persons professionally arranging or executing crypto-asset transactions must maintain arrangements, systems and procedures to prevent, detect and report market abuse, and submit suspicious transaction and order reports (STORs) on the prescribed templates, per Delegated Regulation (EU) 2025/885.",
     "criticality": "important", "applicable_entity": "CASP / trading platform",
     "level": "L2", "instrument": "Commission Delegated Regulation (EU) 2025/885"},
    {"article": "RTS 2025/1142 (CASP conflicts)",
     "requirement_text": "CASPs must establish, maintain and disclose conflict-of-interest policies and procedures per Delegated Regulation (EU) 2025/1142.",
     "criticality": "important", "applicable_entity": "CASP",
     "level": "L2", "instrument": "Commission Delegated Regulation (EU) 2025/1142"},
    {"article": "RTS 2025/1141 (ART conflicts)",
     "requirement_text": "Issuers of asset-referenced tokens must establish, maintain and disclose conflict-of-interest policies and procedures per Delegated Regulation (EU) 2025/1141.",
     "criticality": "important", "applicable_entity": "ART issuer",
     "level": "L2", "instrument": "Commission Delegated Regulation (EU) 2025/1141"},
    {"article": "RTS 2025/422 (sustainability)",
     "requirement_text": "White papers must disclose sustainability indicators on the principal adverse impacts of the consensus mechanism on the climate and the environment (white-paper Part J), per Delegated Regulation (EU) 2025/422.",
     "criticality": "recommended", "applicable_entity": "white-paper preparers (ART/EMT/OTHR)",
     "level": "L2", "instrument": "Commission Delegated Regulation (EU) 2025/422"},
    {"article": "RTS 2025/413-414 (qualifying holding)",
     "requirement_text": "A proposed direct or indirect acquisition of a qualifying holding in a CASP or in an ART issuer must be notified and assessed on the information set out in Delegated Regulations (EU) 2025/413 (CASP) and (EU) 2025/414 (ART issuer).",
     "criticality": "recommended", "applicable_entity": "CASP / ART issuer / acquirers",
     "level": "L2", "instrument": "Commission Delegated Regulations (EU) 2025/413 and 2025/414"},
    {"article": "ESMA public registers (5 CSVs)",
     "requirement_text": "Verify counterparties and market status against the ESMA MiCA public registers, published as five weekly CSV extracts: authorised CASPs (CASPS), ART issuers (ARTZZ), e-money-token issuers and white papers (EMTWP), other-crypto-asset white papers (OTHER) and the non-compliant-entities warning list (NCASP). Providing crypto-asset services without authorisation leads to NCASP listing by the national competent authority.",
     "criticality": "recommended", "applicable_entity": "all crypto market participants",
     "level": "L3", "instrument": "MiCA Arts 109-110 (ESMA interim register CSVs)"},
]


def main():
    db = SessionLocal()
    try:
        existing = {r.article for r in db.query(LawRequirement).filter(
            LawRequirement.cluster_id == MICA_CLUSTER_ID).all()}
        bad = [r["article"] for r in REQUIREMENTS if len(r["article"]) > 50] + \
              [r["applicable_entity"] for r in REQUIREMENTS if len(r["applicable_entity"]) > 50]
        if bad:
            print("ABORT: >50 chars:", bad); sys.exit(1)
        added = 0
        for r in REQUIREMENTS:
            if r["article"] in existing:
                print(f"[skip] already present: {r['article']}"); continue
            db.add(LawRequirement(
                law_id=MICA_LAW_ID, cluster_id=MICA_CLUSTER_ID,
                article=r["article"], requirement_text=r["requirement_text"],
                criticality=r["criticality"], applicable_entity=r["applicable_entity"],
                deadline=r.get("deadline"),
                extra_metadata={"level": r["level"], "instrument": r["instrument"],
                                "source": SRC, "layer": "ESMA/EBA Level 2/3"},
            ))
            added += 1
        db.commit()
        print(f"[OK] added {added} Level 2/3 requirements to cluster {MICA_CLUSTER_ID} "
              f"(law_id {MICA_LAW_ID}); total now "
              f"{db.query(LawRequirement).filter(LawRequirement.cluster_id==MICA_CLUSTER_ID).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
