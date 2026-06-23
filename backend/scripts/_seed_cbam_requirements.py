"""Seed the canonical headline obligations of Reg (EU) 2023/956 (CBAM) into law_requirements.

Pre-curated from a full sequential read of the regulation (116 recitals, 36 articles,
6 annexes) — Brubru canon project, 23 June 2026. The Formex parser leaves the body XML
without clean article text for multi-file laws, so the AI extractor returns 0; pre-seeding
guarantees EU Law Comply can produce a complete compliance report for any EU importer of
CBAM goods.

IDs set after running _ingest_cbam_oneshot.py + create_law_clusters.py --package cbam:
  SELECT id, celex FROM eu_laws WHERE celex='32023R0956';   -> 25641
  SELECT id, name FROM law_clusters WHERE name LIKE 'CBAM%'; -> 54
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

CBAM_LAW_ID = 25641
CBAM_CLUSTER_ID = 54

REQUIREMENTS = [
    {
        "article": "Article 2 + Annex I",
        "requirement_text": (
            "CBAM applies to goods originating in a third country and listed in Annex I by Combined "
            "Nomenclature (CN) code, across six sectors: cement, electricity, fertilisers, iron & steel, "
            "aluminium and hydrogen. Goods of negligible value (intrinsic value not exceeding EUR 150 per "
            "consignment), goods in travellers' personal luggage and goods for military use are excluded, "
            "as are goods originating in the Annex III countries/territories (Iceland, Liechtenstein, "
            "Norway, Switzerland; Büsingen, Heligoland, Livigno, Ceuta, Melilla)."
        ),
        "criticality": "important",
        "applicable_entity": "importer of CBAM goods",
    },
    {
        "article": "Article 4 / Article 25(1)",
        "requirement_text": (
            "From 1 January 2026, goods listed in Annex I may be imported into the customs territory of the "
            "Union only by an authorised CBAM declarant. Customs authorities shall not allow importation of "
            "covered goods by any person other than an authorised CBAM declarant."
        ),
        "criticality": "critical",
        "applicable_entity": "importer of CBAM goods",
    },
    {
        "article": "Article 5",
        "requirement_text": (
            "Before importing covered goods, an importer established in a Member State (or its indirect "
            "customs representative, mandatory where the importer is not established in a Member State) "
            "shall apply via the CBAM registry for the status of authorised CBAM declarant, providing name/"
            "address/EORI number, main economic activity, a tax-good-standing certificate, a declaration of "
            "honour on the absence of serious infringements, evidence of financial and operational capacity, "
            "and estimated import values/volumes by type of goods."
        ),
        "criticality": "critical",
        "applicable_entity": "importer / indirect customs representative",
    },
    {
        "article": "Article 17(5)",
        "requirement_text": (
            "Where the applicant was not established throughout the two financial years preceding the "
            "application, the competent authority shall require a guarantee (bank guarantee payable at first "
            "demand, or equivalent) set at the aggregate value of the CBAM certificates the declarant would "
            "have to surrender for the reported imports. The guarantee is released after 31 May of the "
            "second year in which the declarant has surrendered certificates."
        ),
        "criticality": "important",
        "applicable_entity": "newly established authorised CBAM declarant",
    },
    {
        "article": "Article 6 / Article 22(1)",
        "requirement_text": (
            "By 31 May of each year, and for the first time in 2027 for the year 2026, each authorised CBAM "
            "declarant shall submit, via the CBAM registry, a CBAM declaration for the preceding calendar "
            "year stating the total quantity of each type of goods (MWh for electricity, tonnes otherwise), "
            "the total verified embedded emissions, and the total number of CBAM certificates to be "
            "surrendered (net of any foreign carbon price under Article 9 and the free-allocation adjustment "
            "under Article 31), with copies of the verification reports; and shall surrender that number of "
            "certificates."
        ),
        "criticality": "critical",
        "applicable_entity": "authorised CBAM declarant",
    },
    {
        "article": "Article 7 + Annex IV",
        "requirement_text": (
            "Embedded emissions shall be calculated using the methods in Annex IV: based on actual emissions "
            "from the production processes where these can be adequately determined, otherwise by reference "
            "to default values. For goods listed in Annex II (iron & steel, aluminium, certain chemicals/"
            "hydrogen) only direct emissions are taken into account in the initial phase; for cement, "
            "fertilisers and electricity both direct and indirect (electricity) emissions count."
        ),
        "criticality": "critical",
        "applicable_entity": "authorised CBAM declarant",
    },
    {
        "article": "Article 8 + Annex VI",
        "requirement_text": (
            "The total embedded emissions declared in the CBAM declaration shall be verified by a verifier "
            "accredited under Implementing Regulation (EU) 2018/2067 or by a national accreditation body, "
            "applying the verification principles in Annex VI."
        ),
        "criticality": "critical",
        "applicable_entity": "authorised CBAM declarant / accredited verifier",
    },
    {
        "article": "Article 9",
        "requirement_text": (
            "A declarant may claim a reduction in the number of CBAM certificates to be surrendered "
            "corresponding to a carbon price effectively paid in the country of origin for the declared "
            "embedded emissions, taking into account any rebate or compensation available. The declarant "
            "shall keep documentation, certified by an independent person, evidencing the carbon price and "
            "its actual payment."
        ),
        "criticality": "important",
        "applicable_entity": "authorised CBAM declarant",
    },
    {
        "article": "Article 7(5)-(6) / Article 9(3)",
        "requirement_text": (
            "The declarant shall keep records of the information used to calculate embedded emissions "
            "(sufficiently detailed for verification and review), including the verifier's report and the "
            "carbon-price documentation, until the end of the fourth year after the year in which the CBAM "
            "declaration has been or should have been submitted."
        ),
        "criticality": "important",
        "applicable_entity": "authorised CBAM declarant",
    },
    {
        "article": "Article 20 / Article 21",
        "requirement_text": (
            "CBAM certificates (each corresponding to one tonne of CO2e) are sold by Member States on a "
            "common central platform at a price equal to the weekly average of the closing prices of EU ETS "
            "allowances on the auction platform, published by the Commission on the first working day of "
            "each week."
        ),
        "criticality": "important",
        "applicable_entity": "authorised CBAM declarant",
    },
    {
        "article": "Article 22(2)",
        "requirement_text": (
            "The authorised CBAM declarant shall ensure that the number of CBAM certificates on its account "
            "at the end of each quarter corresponds to at least 80% of the embedded emissions (determined by "
            "reference to default values) in all goods imported since the beginning of the calendar year."
        ),
        "criticality": "critical",
        "applicable_entity": "authorised CBAM declarant",
    },
    {
        "article": "Article 23 / Article 24",
        "requirement_text": (
            "A declarant may request repurchase of excess certificates after the annual surrender, capped at "
            "one third of the certificates purchased during the previous calendar year, at the original "
            "purchase price (request by 30 June). On 1 July each year the Commission cancels, without "
            "compensation, any certificates purchased during the year before the previous calendar year that "
            "remain on the account."
        ),
        "criticality": "informational",
        "applicable_entity": "authorised CBAM declarant",
    },
    {
        "article": "Article 31",
        "requirement_text": (
            "The number of CBAM certificates to be surrendered is adjusted downward to reflect the extent to "
            "which EU ETS allowances are still allocated free of charge under Article 10a of Directive "
            "2003/87/EC to Union installations producing the same goods. CBAM phases in as ETS free "
            "allocation is phased out over 2026-2034."
        ),
        "criticality": "important",
        "applicable_entity": "authorised CBAM declarant",
    },
    {
        "article": "Article 26",
        "requirement_text": (
            "An authorised CBAM declarant who fails to surrender, by 31 May, the required number of "
            "certificates is liable for a penalty per missing certificate identical to the EU ETS excess-"
            "emissions penalty (Article 16(3) and (4) of Directive 2003/87/EC). A person other than an "
            "authorised CBAM declarant who introduces covered goods without complying is liable for a "
            "penalty of three to five times that amount. Payment of the penalty does not release the "
            "declarant from the obligation to surrender the outstanding certificates."
        ),
        "criticality": "critical",
        "applicable_entity": "importer of CBAM goods",
    },
    {
        "article": "Article 27",
        "requirement_text": (
            "Practices of circumvention are prohibited and monitored: a change in the pattern of trade with "
            "insufficient due cause other than to avoid CBAM obligations, including slightly modifying goods "
            "to fall under CN codes not listed in Annex I (without altering their essential characteristics) "
            "or artificially splitting shipments to stay under the negligible-value threshold. The Commission "
            "may extend Annex I to slightly modified products for anti-circumvention purposes."
        ),
        "criticality": "important",
        "applicable_entity": "importer of CBAM goods / third-country operator",
    },
    {
        "article": "Article 10",
        "requirement_text": (
            "An operator of a production installation in a third country may request registration of the "
            "installation in the CBAM registry, determine and have verified its embedded emissions, keep the "
            "records for four years, and disclose the verified information to authorised CBAM declarants, who "
            "may then rely on it to meet their verification obligation under Article 8."
        ),
        "criticality": "informational",
        "applicable_entity": "third-country installation operator",
    },
    {
        "article": "Articles 32-35 (transitional period, now closed)",
        "requirement_text": (
            "During the transitional period from 1 October 2023 to 31 December 2025 obligations were limited "
            "to reporting: each importer (or indirect customs representative) submitted a quarterly CBAM "
            "report within one month of each quarter-end, declaring embedded direct and indirect emissions "
            "and any carbon price paid abroad, with no financial adjustment. The final transitional report "
            "(Q4 2025) was due 31 January 2026."
        ),
        "criticality": "informational",
        "applicable_entity": "importer of CBAM goods (historic)",
    },
]


def main():
    if CBAM_LAW_ID is None or CBAM_CLUSTER_ID is None:
        print("ABORT: CBAM_LAW_ID / CBAM_CLUSTER_ID not set.")
        sys.exit(1)

    db = SessionLocal()
    try:
        existing = db.query(LawRequirement).filter(LawRequirement.law_id == CBAM_LAW_ID).count()
        if existing:
            print(f"[INFO] {existing} requirements already exist for law_id={CBAM_LAW_ID}. Skipping.")
            return
        for r in REQUIREMENTS:
            db.add(LawRequirement(
                law_id=CBAM_LAW_ID,
                cluster_id=CBAM_CLUSTER_ID,
                article=r["article"],
                requirement_text=r["requirement_text"],
                criticality=r["criticality"],
                applicable_entity=r["applicable_entity"],
            ))
        db.commit()
        print(f"[OK] seeded {len(REQUIREMENTS)} requirements for law_id={CBAM_LAW_ID}, cluster_id={CBAM_CLUSTER_ID}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
