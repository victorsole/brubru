"""Seed the canonical headline obligations of Reg (EU) 2024/2754 into law_requirements.

The Regulation has only 3 articles (+ 1 Annex), but the operative obligations sit across
Article 1 (multi-paragraph duty imposition) and Article 2 (release of provisional duty
securities). The AI extractor will typically catch some of these, but pre-seeding ensures
EU Law Comply can produce a complete compliance report for any EU importer of Chinese BEVs.

Pre-curated from a full sequential read of the regulation + the analysis at
data/canon/2024-2754_china_bev_duties.analysis.md (Brubru canon project, May 2026).

TODO: After running `_ingest_china_bev_oneshot.py`, replace BEV_LAW_ID / BEV_CLUSTER_ID
below with the actual ids assigned by the DB. Verify with:
  SELECT id, celex FROM eu_laws WHERE celex='32024R2754';
  SELECT id, name FROM law_clusters WHERE name LIKE 'China BEV%';
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from backend.core.database import SessionLocal
from backend.models.eu_law import LawRequirement

# Set 15 May 2026 after running ingest + create_law_clusters
BEV_LAW_ID = 214
BEV_CLUSTER_ID = 23

REQUIREMENTS = [
    {
        "article": "Article 1(1)",
        "requirement_text": (
            "Importers shall pay a definitive additional countervailing duty on imports of new battery "
            "electric vehicles for passenger transport (CN ex 8703 80 10, TARIC 8703 80 10 10) originating "
            "in the People's Republic of China. The duty is expressed as an ad valorem rate on the CIF "
            "value at the EU border and applies on top of the conventional 6.5% MFN customs duty."
        ),
        "criticality": "critical",
        "applicable_entity": "importer of Chinese BEVs",
    },
    {
        "article": "Article 1(2)",
        "requirement_text": (
            "The applicable rate depends on the exporting producer group: BYD Group 17.0% "
            "(TARIC C184); Geely Group 18.8% (C185-C187 by entity); SAIC Group 35.3% (C188); "
            "Tesla (Shanghai) Co., Ltd 7.8% (C189); other cooperating companies named in the Annex "
            "20.7% (C190); all other companies 35.3% (C179). The combined total landed duty therefore "
            "ranges from 14.3% (Tesla Shanghai) to 41.8% (SAIC, non-cooperating)."
        ),
        "criticality": "critical",
        "applicable_entity": "importer of Chinese BEVs",
    },
    {
        "article": "Article 1(3)",
        "requirement_text": (
            "To benefit from the individual producer duty rate (rather than the 35.3% 'all other "
            "companies' default), the importer shall present to Member State customs authorities a "
            "valid commercial invoice on which appears a dated and signed declaration by an official "
            "of the producing entity, certifying that the vehicles were manufactured by the named "
            "producer at its specified address with its TARIC additional code, and that the invoice "
            "information is complete and correct. Without the valid invoice, the 35.3% rate applies."
        ),
        "criticality": "critical",
        "applicable_entity": "importer of Chinese BEVs",
    },
    {
        "article": "Article 1(4)",
        "requirement_text": (
            "Unless otherwise specified, the provisions in force concerning customs duties apply. "
            "This means standard Union Customs Code (Reg (EU) 952/2013) rules on origin determination, "
            "customs value calculation, customs procedures (release for free circulation, customs "
            "warehousing, etc.), and TARIC integration apply alongside this Regulation."
        ),
        "criticality": "important",
        "applicable_entity": "importer of Chinese BEVs",
    },
    {
        "article": "Article 2",
        "requirement_text": (
            "Amounts secured by way of provisional countervailing duties under Commission "
            "Implementing Regulation (EU) 2024/1866 (provisional duties from 8 July 2024) shall be "
            "definitively released to importers. This is a consequence of the threat-of-injury finding "
            "(Article 8(8) of the Basic Regulation, Reg (EU) 2016/1037) and the consequent application "
            "of Article 16(2) — which forbids retroactive collection where actual material injury is "
            "not established. Importers shall apply to their Member State customs authority for release."
        ),
        "criticality": "important",
        "applicable_entity": "importer of Chinese BEVs / customs authority",
    },
    {
        "article": "Article 3 / Article 16(4) Basic Regulation",
        "requirement_text": (
            "No retroactive countervailing duties apply to imports made between the start of "
            "registration (6 March 2024 under Reg (EU) 2024/785) and the entry into force of "
            "provisional duties. The conditions of Article 16(4) of the Basic Regulation (critical "
            "circumstances, massive imports, risk of undermining definitive measures) were not met. "
            "Imports during the registration period are duty-free for these CVD purposes."
        ),
        "criticality": "important",
        "applicable_entity": "importer of Chinese BEVs",
    },
    {
        "article": "Annex (entity list)",
        "requirement_text": (
            "To qualify for the 20.7% 'other cooperating companies' rate (TARIC additional code C190) "
            "rather than the 35.3% default, the exporting producer must be specifically named in the "
            "Annex to this Regulation. Producers not listed in the Annex AND not in the BYD / Geely / "
            "SAIC / Tesla (Shanghai) individual-rate groups are subject to the 35.3% all-other rate."
        ),
        "criticality": "critical",
        "applicable_entity": "Chinese exporting producer",
    },
    {
        "article": "Article 23 Basic Regulation (anti-circumvention)",
        "requirement_text": (
            "Circumvention practices — including assembly operations in third countries from Chinese "
            "kits/components where the value-added is below the threshold; minor product modifications "
            "to fall outside the CN code; channelling exports through low-rate producers without "
            "genuine production; absorption of duty by exporters/related importers — may trigger an "
            "anti-circumvention investigation under Article 23 of the Basic Regulation. Extension of "
            "duties to circumventing imports is the typical remedy."
        ),
        "criticality": "important",
        "applicable_entity": "Chinese exporting producer / EU related importer",
    },
    {
        "article": "Article 18 Basic Regulation (expiry review)",
        "requirement_text": (
            "Definitive countervailing duties expire 5 years after entry into force (default 31 October "
            "2029) unless an expiry review is initiated before expiry on a duly substantiated request by "
            "or on behalf of the EU industry. The Commission shall publish a notice of impending expiry "
            "in the Official Journal at an appropriate time in the last year of the duty period."
        ),
        "criticality": "informational",
        "applicable_entity": "EU industry / European Commission",
    },
    {
        "article": "Article 19 Basic Regulation (interim review)",
        "requirement_text": (
            "An interim review of the duties may be requested by any interested party showing a change "
            "of circumstances of a lasting nature (e.g. termination of a subsidy programme, new evidence "
            "on subsidy rates). Interim reviews may result in repeal, modification or maintenance of the "
            "duties."
        ),
        "criticality": "informational",
        "applicable_entity": "interested party (importer / exporter / EU producer / GOC)",
    },
    {
        "article": "Article 21 Basic Regulation (refunds)",
        "requirement_text": (
            "An importer may apply for refund of duties paid where it can demonstrate that the subsidy "
            "rate applicable to the actual producer of its imports, on the basis of which duties were "
            "collected, has been eliminated or reduced. Applications shall be submitted within six months "
            "of the date on which the amount of duty was duly determined."
        ),
        "criticality": "informational",
        "applicable_entity": "importer of Chinese BEVs",
    },
    {
        "article": "Article 13 Basic Regulation (price undertakings)",
        "requirement_text": (
            "Although all five undertaking offers received during this investigation (CCCME collective, "
            "BYD, Geely, SAIC, other cooperating) were rejected, exporting producers remain entitled to "
            "submit new undertaking offers at later procedural stages (e.g. interim review, expiry "
            "review). Any such offer must address the rejection grounds: product complexity / "
            "monitoring risk / cooperation / coverage / WTO-compatibility."
        ),
        "criticality": "informational",
        "applicable_entity": "Chinese exporting producer",
    },
]


def main():
    if BEV_LAW_ID is None or BEV_CLUSTER_ID is None:
        print("ABORT: BEV_LAW_ID / BEV_CLUSTER_ID not set. Run ingest + create_law_clusters first, then patch this file.")
        sys.exit(1)

    db = SessionLocal()
    try:
        existing = db.query(LawRequirement).filter(LawRequirement.law_id == BEV_LAW_ID).count()
        if existing:
            print(f"[INFO] {existing} requirements already exist for law_id={BEV_LAW_ID}. Skipping.")
            return
        for r in REQUIREMENTS:
            db.add(LawRequirement(
                law_id=BEV_LAW_ID,
                cluster_id=BEV_CLUSTER_ID,
                article=r["article"],
                requirement_text=r["requirement_text"],
                criticality=r["criticality"],
                applicable_entity=r["applicable_entity"],
            ))
        db.commit()
        print(f"[OK] seeded {len(REQUIREMENTS)} requirements for law_id={BEV_LAW_ID}, cluster_id={BEV_CLUSTER_ID}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
