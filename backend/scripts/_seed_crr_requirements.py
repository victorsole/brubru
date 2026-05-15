"""Seed the canonical CRR (32013R0575) headline obligations into law_requirements.

The Formex parser couldn't extract article text from CRR's XML, so the AI extractor
returned 0 requirements. This seeds the 18 headline obligations any bank compliance
team checks against — Pillar 1 ratios, large exposures, liquidity, leverage,
disclosure, governance, and ongoing reporting.

Pre-curated from the full sequential read of CRR (Brubru canon project, May 2026).
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

CRR_LAW_ID = 22933   # CRR row in eu_laws
CRR_CLUSTER_ID = 22  # CRR cluster in law_clusters

REQUIREMENTS = [
    {
        "article": "Article 92(1)(a)",
        "requirement_text": "Institutions shall at all times maintain a Common Equity Tier 1 (CET1) capital ratio of at least 4.5% of the total risk exposure amount (RWAs).",
        "criticality": "critical",
        "applicable_entity": "credit institution / investment firm",
    },
    {
        "article": "Article 92(1)(b)",
        "requirement_text": "Institutions shall at all times maintain a Tier 1 capital ratio of at least 6% of the total risk exposure amount.",
        "criticality": "critical",
        "applicable_entity": "credit institution / investment firm",
    },
    {
        "article": "Article 92(1)(c)",
        "requirement_text": "Institutions shall at all times maintain a total capital ratio of at least 8% of the total risk exposure amount. Total capital = Tier 1 (CET1 + AT1) + Tier 2.",
        "criticality": "critical",
        "applicable_entity": "credit institution / investment firm",
    },
    {
        "article": "Article 93",
        "requirement_text": "The own funds of an institution may not fall below the amount of initial capital required at the time of authorisation under CRD IV (EUR 5 million for credit institutions).",
        "criticality": "critical",
        "applicable_entity": "credit institution / investment firm",
    },
    {
        "article": "Article 99(1)",
        "requirement_text": "Institutions shall report own funds and capital adequacy (COREP) to competent authorities at least on a semi-annual basis using uniform EBA reporting formats.",
        "criticality": "important",
        "applicable_entity": "credit institution / investment firm",
    },
    {
        "article": "Article 178",
        "requirement_text": "An obligor is in default when (a) the institution considers it unlikely to pay its credit obligations in full without recourse to realising security, OR (b) the obligor is past due more than 90 days on a material credit obligation. Member State CAs may set 180 days for residential mortgage, SME commercial real estate retail, and public sector entity exposures.",
        "criticality": "critical",
        "applicable_entity": "credit institution / investment firm",
    },
    {
        "article": "Article 395(1)",
        "requirement_text": "An institution shall not incur an exposure (after CRM) to a client or group of connected clients exceeding 25% of its eligible capital. Where the client is an institution (or institution-including group), the limit is the higher of 25% eligible capital or EUR 150 million, capped at 100% of eligible capital.",
        "criticality": "critical",
        "applicable_entity": "credit institution / investment firm",
    },
    {
        "article": "Article 394",
        "requirement_text": "Institutions shall report each large exposure (≥ 10% of eligible capital, per Article 392) to competent authorities at least semi-annually, including the top 20 largest consolidated exposures, top 10 to institutions, and top 10 to unregulated financial entities.",
        "criticality": "important",
        "applicable_entity": "credit institution / investment firm",
    },
    {
        "article": "Article 405",
        "requirement_text": "An institution may be exposed to a securitisation only if the originator, sponsor, or original lender retains a material net economic interest of at least 5% on an ongoing basis. Retention must be in one of five qualifying forms (vertical 5% slice, originator's interest, random 5% selection, first-loss tranche, first-loss per exposure) and cannot be hedged or sold.",
        "criticality": "critical",
        "applicable_entity": "credit institution / investment firm acting as securitisation investor",
    },
    {
        "article": "Article 406",
        "requirement_text": "Before becoming exposed to a securitisation, institutions must demonstrate comprehensive understanding through formal due-diligence policies covering retention disclosure, position risk characteristics, underlying exposures' risk, originator/sponsor reputation, methodologies, valuation of collateral, structural features, and ongoing performance monitoring (30/60/90 days past due, default rates, LTV distributions).",
        "criticality": "important",
        "applicable_entity": "credit institution / investment firm acting as securitisation investor",
    },
    {
        "article": "Article 412(1)",
        "requirement_text": "Institutions shall hold a stock of liquid assets covering net liquidity outflows under a 30-day stressed scenario (Liquidity Coverage Requirement / LCR). Phased in 60%-70%-80%-100% from 2015 to 2018; binding 100% LCR from 1 January 2018 (as specified by Commission Delegated Regulation 2015/61).",
        "criticality": "critical",
        "applicable_entity": "credit institution",
    },
    {
        "article": "Article 413(1)",
        "requirement_text": "Institutions shall ensure that long-term obligations are met with a diversity of stable funding instruments under both normal and stressed conditions (NSFR principle). Binding 100% Net Stable Funding Ratio introduced by CRR II (Regulation (EU) 2019/876).",
        "criticality": "important",
        "applicable_entity": "credit institution",
    },
    {
        "article": "Article 429",
        "requirement_text": "Institutions shall calculate a leverage ratio as Tier 1 capital divided by total exposure measure (assets + off-balance items + derivatives + SFTs), with no credit risk mitigation, collateral, or netting reductions. Made binding at 3% by CRR II from 28 June 2021.",
        "criticality": "critical",
        "applicable_entity": "credit institution / investment firm",
    },
    {
        "article": "Article 431",
        "requirement_text": "Institutions shall publicly disclose the Pillar 3 information laid down in Articles 435-455, adopt a formal disclosure policy, and assess whether disclosures convey the institution's risk profile comprehensively to market participants.",
        "criticality": "important",
        "applicable_entity": "credit institution / investment firm",
    },
    {
        "article": "Article 433",
        "requirement_text": "Pillar 3 disclosures shall be published at least annually, in conjunction with the financial statements. Institutions shall assess the need for more frequent disclosure of items prone to rapid change (own funds, capital requirements, leverage, risk exposure).",
        "criticality": "important",
        "applicable_entity": "credit institution / investment firm",
    },
    {
        "article": "Article 450",
        "requirement_text": "Institutions shall publicly disclose remuneration policy and practices for identified staff whose professional activities have a material impact on the risk profile, including: decision-making process, pay-performance link, fixed-to-variable ratios (capped per CRD IV Article 94(1)(g)), aggregate quantitative data by senior management and material risk-takers, and the number of individuals remunerated EUR 1 million or more broken down into EUR 500,000 / EUR 1 million bands.",
        "criticality": "important",
        "applicable_entity": "credit institution / investment firm",
    },
    {
        "article": "Article 451",
        "requirement_text": "Institutions shall disclose the leverage ratio calculated under Article 429, a breakdown of the total exposure measure, reconciliation with published financial statements, the processes used to manage risk of excessive leverage, and the factors that impacted the leverage ratio during the reporting period.",
        "criticality": "important",
        "applicable_entity": "credit institution / investment firm",
    },
    {
        "article": "Article 501",
        "requirement_text": "For SME exposures (retail, corporate, or real-estate-secured) where total exposure to the obligor or group of connected clients does not exceed EUR 1.5 million, institutions shall multiply the calculated capital requirement by the SME Supporting Factor of 0.7619 (effective ~23.81% capital reduction).",
        "criticality": "recommended",
        "applicable_entity": "credit institution / investment firm with SME exposures",
    },
]


def main():
    db = SessionLocal()
    try:
        # Skip if already seeded (idempotent)
        existing = db.query(LawRequirement).filter(
            LawRequirement.cluster_id == CRR_CLUSTER_ID,
            LawRequirement.law_id == CRR_LAW_ID,
        ).count()
        if existing > 0:
            print(f"already seeded ({existing} requirements in cluster {CRR_CLUSTER_ID}); skipping")
            return

        for r in REQUIREMENTS:
            req = LawRequirement(
                law_id=CRR_LAW_ID,
                cluster_id=CRR_CLUSTER_ID,
                article=r["article"],
                requirement_text=r["requirement_text"],
                criticality=r["criticality"],
                applicable_entity=r["applicable_entity"],
            )
            db.add(req)
        db.commit()
        n = db.query(LawRequirement).filter(LawRequirement.cluster_id == CRR_CLUSTER_ID).count()
        print(f"seeded {len(REQUIREMENTS)} CRR requirements; cluster {CRR_CLUSTER_ID} now has {n} requirements")
    finally:
        db.close()


if __name__ == "__main__":
    main()
