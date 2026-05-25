"""Seed the canonical headline obligations of Reg (EU) 2022/433 into law_requirements.

The Regulation has 4 articles plus 2 Annexes. The operative obligations sit across Article 1
(definitive countervailing duty + commercial-invoice condition), Article 2 (amendment of the
parallel anti-dumping Regulation 2021/2012), and Article 3 (interaction with the steel
safeguard). Pre-seeding ensures EU Law Comply can produce a complete compliance report for any
EU importer of stainless steel cold-rolled flat products from India or Indonesia.

Pre-curated from a full sequential read of the regulation + the analysis at
data/canon/2022-433_india_indonesia_stainless_steel.analysis.md (Brubru canon project, May 2026).

ids verified live against prod Supabase on 25 May 2026:
  SELECT id, celex FROM eu_laws WHERE celex='32022R0433';   -> 17319
  SELECT id, name FROM law_clusters WHERE name LIKE '%Stainless Steel%';  -> 24
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

SSCR_LAW_ID = 17319
SSCR_CLUSTER_ID = 24

REQUIREMENTS = [
    {
        "article": "Article 1(1)",
        "requirement_text": (
            "Importers shall pay a definitive countervailing duty on imports of flat-rolled products "
            "of stainless steel, not further worked than cold-rolled (SSCR), originating in India and "
            "Indonesia. The product is covered by 19 CN codes in headings 7219 and 7220. The duty is "
            "expressed as an ad valorem rate on the net, free-at-Union-frontier price before duty."
        ),
        "criticality": "critical",
        "applicable_entity": "importer of SSCR from India or Indonesia",
    },
    {
        "article": "Article 1(2) - India",
        "requirement_text": (
            "Indian producer rates: Jindal Stainless Limited 4.3% (TARIC C654); Jindal Stainless Hisar "
            "Limited 4.3% (C655); Chromeni Steels Private Limited 7.5% (C656); all other Indian "
            "companies 7.5% (C999)."
        ),
        "criticality": "critical",
        "applicable_entity": "importer of SSCR from India",
    },
    {
        "article": "Article 1(2) - Indonesia",
        "requirement_text": (
            "Indonesian producer rates: PT. Indonesia Ruipu Nickel and Chrome Alloy (IRNC) 21.4% "
            "(TARIC C657); PT. Jindal Stainless Indonesia 0% (C658, subsidy margin below de minimis); "
            "non-sampled cooperating company 13.5% (see Annex 2); all other Indonesian companies 20.5% "
            "(C999)."
        ),
        "criticality": "critical",
        "applicable_entity": "importer of SSCR from Indonesia",
    },
    {
        "article": "Article 1(3)",
        "requirement_text": (
            "To benefit from an individual producer duty rate (rather than the 'all other companies' "
            "default), the importer shall present to Member State customs authorities a valid commercial "
            "invoice bearing a dated and signed declaration by an official of the issuing entity, "
            "identifying the producer, its address and TARIC additional code, and certifying that the "
            "invoice information is complete and correct. Without that invoice, the all-other-companies "
            "rate applies."
        ),
        "criticality": "critical",
        "applicable_entity": "importer of SSCR from India or Indonesia",
    },
    {
        "article": "Article 1(4)",
        "requirement_text": (
            "Unless otherwise specified, the provisions in force concerning customs duties apply. "
            "Standard Union Customs Code (Reg (EU) 952/2013) rules on origin, customs value, customs "
            "procedures and TARIC integration apply alongside this Regulation."
        ),
        "criticality": "important",
        "applicable_entity": "importer of SSCR from India or Indonesia",
    },
    {
        "article": "Article 1(5)",
        "requirement_text": (
            "Where the countervailing duty has been subtracted from the anti-dumping duty for certain "
            "exporting producers, refund requests under Article 21 of Regulation (EU) 2016/1037 shall "
            "also trigger an assessment of the dumping margin for that exporting producer prevailing "
            "during the refund investigation period."
        ),
        "criticality": "important",
        "applicable_entity": "importer of SSCR from India or Indonesia",
    },
    {
        "article": "Article 2 (amends Reg 2021/2012)",
        "requirement_text": (
            "The parallel anti-dumping duties (Reg (EU) 2021/2012) are amended and run in parallel with "
            "the countervailing duties. Anti-dumping rates after avoiding double counting of export "
            "subsidies (Article 24(1)): India Jindal entities 10.0%, Chromeni and all other Indian "
            "35.3%; Indonesia IRNC 9.3%, Jindal Indonesia 20.2%, other cooperating and all other "
            "Indonesian 19.3%. Combined countervailing + anti-dumping reaches 42.8% for Chromeni."
        ),
        "criticality": "critical",
        "applicable_entity": "importer of SSCR from India or Indonesia",
    },
    {
        "article": "Article 2(2) (anti-dumping uplift safeguard)",
        "requirement_text": (
            "Should the definitive countervailing duties imposed by Article 1 be modified or removed, "
            "the anti-dumping duties in Reg (EU) 2021/2012 shall be increased by the same proportion, "
            "limited to the actual dumping margin or injury margin per company, from the entry into "
            "force of this Regulation. This prevents a gap in protection if the CVD is later changed."
        ),
        "criticality": "important",
        "applicable_entity": "importer of SSCR from India or Indonesia",
    },
    {
        "article": "Article 3 (steel safeguard interaction)",
        "requirement_text": (
            "SSCR is covered by the EU steel safeguard (Reg (EU) 2019/159, prolonged to 30 June 2024). "
            "Where the above-quota safeguard tariff applies and exceeds the combined countervailing and "
            "anti-dumping duty, only the safeguard duty is collected and collection of the AD/CVD is "
            "suspended for the safeguard period. Where it is lower, the safeguard duty is collected plus "
            "the difference up to the higher of the AD/CVD."
        ),
        "criticality": "important",
        "applicable_entity": "importer of SSCR from India or Indonesia / customs authority",
    },
    {
        "article": "Article 4 (entry into force)",
        "requirement_text": (
            "The Regulation entered into force on the day following its publication in the Official "
            "Journal (OJ L 88, 15 March 2022). It is binding in its entirety and directly applicable in "
            "all Member States; no national transposition is required."
        ),
        "criticality": "informational",
        "applicable_entity": "all EU operators / Member State authorities",
    },
    {
        "article": "Article 14(5) Basic Regulation (de minimis)",
        "requirement_text": (
            "PT. Jindal Stainless Indonesia received a 0% duty because its subsidy margin (0.02%) was "
            "below the de minimis threshold of Article 14(5) of the Basic Regulation. Imports of SSCR "
            "produced by Jindal Indonesia (TARIC C658) are therefore not subject to countervailing duty, "
            "though they remain subject to the parallel anti-dumping duty (20.2%)."
        ),
        "criticality": "important",
        "applicable_entity": "importer of SSCR produced by Jindal Indonesia",
    },
    {
        "article": "Special monitoring clause (recitals 1070-1076)",
        "requirement_text": (
            "Should exports by a company benefiting from a lower individual rate increase significantly "
            "in volume after the measures, this may be treated as a change in the pattern of trade and "
            "trigger an anti-circumvention investigation under Article 23 of the Basic Regulation. "
            "Customs authorities must apply usual checks in addition to the commercial invoice."
        ),
        "criticality": "important",
        "applicable_entity": "Indian / Indonesian exporting producer / EU related importer",
    },
    {
        "article": "Article 18 Basic Regulation (expiry review)",
        "requirement_text": (
            "Definitive countervailing duties expire 5 years after entry into force unless an expiry "
            "review is initiated before expiry on a duly substantiated request by or on behalf of the "
            "EU industry. The Commission publishes a notice of impending expiry in the Official Journal "
            "in the last year of the duty period."
        ),
        "criticality": "informational",
        "applicable_entity": "EU industry / European Commission",
    },
    {
        "article": "Article 19 Basic Regulation (interim review)",
        "requirement_text": (
            "An interim review of the duties may be requested by any interested party showing a change "
            "of circumstances of a lasting nature (e.g. termination of a subsidy programme such as the "
            "nickel-ore export restrictions, or new subsidy-rate evidence). Interim reviews may result "
            "in repeal, modification or maintenance of the duties."
        ),
        "criticality": "informational",
        "applicable_entity": "interested party (importer / exporter / EU producer / GOI / GOID)",
    },
    {
        "article": "Article 21 Basic Regulation (refunds)",
        "requirement_text": (
            "An importer may apply for refund of duties paid where it can demonstrate that the subsidy "
            "rate applicable to the actual producer of its imports has been eliminated or reduced. "
            "Applications shall be submitted within six months of the date on which the amount of duty "
            "was duly determined."
        ),
        "criticality": "informational",
        "applicable_entity": "importer of SSCR from India or Indonesia",
    },
]


def main():
    if SSCR_LAW_ID is None or SSCR_CLUSTER_ID is None:
        print("ABORT: SSCR_LAW_ID / SSCR_CLUSTER_ID not set.")
        sys.exit(1)

    db = SessionLocal()
    try:
        existing = db.query(LawRequirement).filter(LawRequirement.law_id == SSCR_LAW_ID).count()
        if existing:
            print(f"[INFO] {existing} requirements already exist for law_id={SSCR_LAW_ID}. Skipping.")
            return
        for r in REQUIREMENTS:
            db.add(LawRequirement(
                law_id=SSCR_LAW_ID,
                cluster_id=SSCR_CLUSTER_ID,
                article=r["article"],
                requirement_text=r["requirement_text"],
                criticality=r["criticality"],
                applicable_entity=r["applicable_entity"],
            ))
        db.commit()
        print(f"[OK] seeded {len(REQUIREMENTS)} requirements for law_id={SSCR_LAW_ID}, cluster_id={SSCR_CLUSTER_ID}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
