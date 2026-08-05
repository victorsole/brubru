"""Seed the canonical headline obligations of Directive (EU) 2025/1892 into law_requirements.

Pre-curated from a full sequential read of the Directive (60 recitals, 4 articles, new Annex IVc,
29 OJ pages) inserting Articles 9a, 22a, 22b, 22c, 22d, 29a and 41a into Directive 2008/98/EC.
Brubru canon project, 5 August 2026. Pre-seeding guarantees EU Law Comply can produce a complete
compliance report even when the AI extractor cannot parse the Formex source cleanly.

IDs verified after running create_law_clusters.py --package textile_epr:
  SELECT id, celex FROM eu_laws WHERE celex='32025L1892';                          -> 15039
  SELECT id, name FROM law_clusters WHERE name='Textile EPR and Food Waste Package'; -> 58

Note on dates: the transposition deadline (17 June 2027, Article 2(1)) and the date by which EPR
schemes must be established (17 April 2028, Article 22a(14)) are DIFFERENT. Both appear below.
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

LAW_ID = 15039
CLUSTER_ID = 58

REQUIREMENTS = [
    {
        "article": "Article 22a(1), Annex IVc",
        "requirement_text": (
            "Producers have extended producer responsibility for the textile, textile-related and "
            "footwear products listed in Annex IVc that they make available on the market for the "
            "first time. Scope is set by Combined Nomenclature code, not by description: Part I "
            "covers CN chapters 61 and 62 in full plus 6301 (excluding 63011000), 6302, 6303, 6304 "
            "(excluding heading 9404), 6309, 6504 and 6505; Part II covers 4203 and footwear codes "
            "6401 to 6405. The headings cover products for household use or other uses where "
            "similar in nature and composition to household use, which includes professional and "
            "workwear uses, except products for professional or military use that pose safety, "
            "health or hygiene risks or raise security concerns."
        ),
        "criticality": "critical",
        "applicable_entity": "Producers of apparel, home textiles and footwear",
    },
    {
        "article": "Article 22a(14)",
        "requirement_text": (
            "Member States shall ensure that extended producer responsibility schemes for textile, "
            "textile-related and footwear products listed in Annex IVc are established by "
            "17 April 2028, in accordance with Articles 8, 8a and 22a to 22d. This is distinct from "
            "the 17 June 2027 transposition deadline in Article 2(1)."
        ),
        "criticality": "critical",
        "applicable_entity": "Member States, PROs",
    },
    {
        "article": "Article 3(4b)",
        "requirement_text": (
            "A producer is any manufacturer, importer, distributor or other natural or legal person "
            "that, whatever the selling technique including distance contracts, either manufactures "
            "Annex IVc products under its own name or trademark in a Member State, resells such "
            "products there under its own name or trademark where the maker's mark does not appear, "
            "supplies them there for the first time on a professional basis from another Member "
            "State or a third country, or sells them by distance contract directly to end users in "
            "a Member State while established elsewhere. Persons supplying used products assessed "
            "as fit for re-use, persons supplying products derived from used or waste products or "
            "their parts, and self-employed tailors producing customised products are excluded."
        ),
        "criticality": "critical",
        "applicable_entity": "Economic operators placing Annex IVc products on an EU market",
    },
    {
        "article": "Article 22a(3)-(4)",
        "requirement_text": (
            "A producer selling by distance contract while established in another Member State must "
            "appoint, by written mandate, an authorised representative established in the Member "
            "State of sale to discharge its extended producer responsibility obligations there. "
            "Member States may extend the same requirement to producers established in third "
            "countries. A producer responsibility organisation may be appointed by written mandate "
            "to meet those obligations on the producer's behalf."
        ),
        "criticality": "critical",
        "applicable_entity": "Distance sellers established outside the Member State of sale",
    },
    {
        "article": "Article 22a(8)",
        "requirement_text": (
            "Producers shall cover the costs of: collection of used products for re-use and separate "
            "collection of waste products for preparing for re-use and recycling; transport for "
            "subsequent sorting and treatment; sorting, preparing for re-use, recycling, other "
            "recovery and disposal; collection, transport and treatment of waste arising from "
            "operations carried out by social economy entities and other actors in the collection "
            "system; compositional surveys of collected mixed municipal waste; information provision "
            "and campaigns on sustainable consumption, waste prevention, re-use, repair and "
            "recycling; data gathering and reporting to competent authorities; and support for "
            "research and development on product design under Article 5 of Regulation (EU) 2024/1781 "
            "and on waste prevention and management with a view to scaling up fibre-to-fibre "
            "recycling. Costs shall not exceed what is necessary to provide those services in a "
            "cost-efficient way."
        ),
        "criticality": "critical",
        "applicable_entity": "Producers of Annex IVc products, PROs",
    },
    {
        "article": "Article 22a(10)-(11)",
        "requirement_text": (
            "Cost coverage applies to products made available on the market for the first time from "
            "16 October 2025 where an extended producer responsibility scheme was already "
            "established in that Member State on that date, and otherwise from the date the Member "
            "State brings its transposing measures into force or, at the latest, from 17 April 2028."
        ),
        "criticality": "high",
        "applicable_entity": "Producers of Annex IVc products",
    },
    {
        "article": "Article 22b",
        "requirement_text": (
            "Producers shall register in the national register of producers of textile, "
            "textile-related and footwear products in each Member State where they make Annex IVc "
            "products available on the market for the first time. Member States shall only allow "
            "such products to be made available where the producer, or its authorised "
            "representative, is registered. Registers shall be publicly accessible, free of charge, "
            "machine readable, sortable and searchable, and the Commission shall maintain a website "
            "linking all national registers."
        ),
        "criticality": "critical",
        "applicable_entity": "Producers, authorised representatives, Member States",
    },
    {
        "article": "Article 22c(1)-(4)",
        "requirement_text": (
            "Producers shall entrust a producer responsibility organisation to fulfil their extended "
            "producer responsibility obligations on their behalf. Producer responsibility "
            "organisations must obtain authorisation from a competent authority and demonstrate the "
            "necessary expertise in waste management and sustainability."
        ),
        "criticality": "critical",
        "applicable_entity": "Producers of Annex IVc products, PROs",
    },
    {
        "article": "Article 22c(5)-(6)",
        "requirement_text": (
            "Financial contributions paid by producers shall be based on weight and, where "
            "appropriate, quantity, and shall be modulated on the basis of the ecodesign "
            "requirements adopted under Regulation (EU) 2024/1781 that are most relevant to waste "
            "prevention and to treatment in line with the waste hierarchy. Contributions shall take "
            "account of revenues from re-use, preparing for re-use and secondary raw materials, and "
            "shall ensure equal treatment of producers regardless of origin or size without "
            "disproportionate burdens on SMEs. Member States may additionally require modulation to "
            "address ultra-fast and fast fashion practices, based on product life span, useful life "
            "beyond the first user, and contribution to closing the loop."
        ),
        "criticality": "high",
        "applicable_entity": "PROs, producers of Annex IVc products",
    },
    {
        "article": "Article 22c(8)-(9)",
        "requirement_text": (
            "Producer responsibility organisations shall establish a separate collection system for "
            "used and waste Annex IVc products regardless of nature, material composition, "
            "condition, name, brand, trademark or origin. Collection shall be free of charge, with "
            "suitable containers provided free of charge, at a frequency adapted to the area and "
            "volume. The system shall cover the whole territory of the Member State taking account "
            "of population size and density, accessibility and vicinity to end users, and shall not "
            "be limited to areas where collection is profitable. It shall maintain a sustained and "
            "technically feasible increase in separate collection with a corresponding decrease in "
            "mixed municipal waste."
        ),
        "criticality": "critical",
        "applicable_entity": "PROs, waste management operators, local authorities",
    },
    {
        "article": "Article 22c(10)-(13)",
        "requirement_text": (
            "Producer responsibility organisations shall not refuse the participation of local "
            "public authorities, social economy entities or other re-use operators in the separate "
            "collection system. Social economy entities may maintain and operate their own separate "
            "collection points, shall receive equal or preferential treatment in the location of "
            "collection points, and shall not be required to hand over collected products to the "
            "producer responsibility organisation. They shall report at least annually to the "
            "competent authority the quantity by weight collected, split between fit for re-use, "
            "destined for preparing for re-use and recycling, and destined for other recovery or "
            "disposal, indicating exports where possible. Member States may exempt them totally or "
            "partially where reporting would be a disproportionate administrative burden."
        ),
        "criticality": "high",
        "applicable_entity": "PROs, social economy entities, re-use operators",
    },
    {
        "article": "Article 22a(13)",
        "requirement_text": (
            "Providers of online platforms allowing consumers to conclude distance contracts with "
            "producers offering Annex IVc products to consumers in the Union shall, before allowing "
            "a producer to use their services, obtain the producer's registration details and "
            "registration number in the register of the Member State where the consumer is located, "
            "and a self-certification committing the producer to offering only products complying "
            "with the extended producer responsibility requirements in that Member State."
        ),
        "criticality": "critical",
        "applicable_entity": "Online platforms under the DSA, producers selling online",
    },
    {
        "article": "Article 22a(15)-(17)",
        "requirement_text": (
            "Producers shall provide fulfilment service providers with their registration and "
            "self-certification information at the moment the service contract is concluded. "
            "Fulfilment service providers shall make best efforts to assess whether that information "
            "is reliable and complete, request correction where it is not, and swiftly suspend "
            "service to the producer where the producer fails to correct, complete or update it, "
            "stating the reasons. Producers are liable for the accuracy of the information. A "
            "suspended producer has the right to challenge the suspension before a court."
        ),
        "criticality": "high",
        "applicable_entity": "Fulfilment service providers, producers selling into the EU",
    },
    {
        "article": "Article 22d(2)-(3)",
        "requirement_text": (
            "Separately collected used and waste textile, textile-related and footwear products are "
            "considered to be waste upon collection. By way of derogation, used products that are "
            "directly handed over by end users and directly professionally assessed as fit for "
            "re-use at the collection point by a re-use operator or social economy entity are not "
            "considered to be waste. The assessment must be professional: the decision may not be "
            "left to the end user."
        ),
        "criticality": "critical",
        "applicable_entity": "Collection points, re-use operators, social economy entities",
    },
    {
        "article": "Article 22d(5)",
        "requirement_text": (
            "Sorting operations shall generate products for re-use and preparing for re-use, "
            "prioritising local sorting and local re-use where appropriate; sort at a granularity "
            "allowing item-to-item separation of fractions fit for direct re-use from those needing "
            "further preparing for re-use, targeting a specific re-use market with up-to-date "
            "criteria; sort items assessed as unsuitable for re-use for remanufacturing and "
            "recycling, including fibre-to-fibre recycling where technology allows, prioritising "
            "remanufacturing over recycling; and produce outputs meeting the end-of-waste criteria "
            "referred to in Article 6."
        ),
        "criticality": "critical",
        "applicable_entity": "Sorting operators, PROs, waste treatment operators",
    },
    {
        "article": "Article 22d(8)-(9)",
        "requirement_text": (
            "Shipments arranged on a professional basis of used products assessed as fit for re-use "
            "shall be accompanied by a copy of the invoice and contract stating the products are "
            "destined for and fit for direct re-use; evidence of a prior sorting operation or direct "
            "professional assessment, as a copy of the records on every bale plus a protocol; and a "
            "declaration that no material in the consignment is waste. Records shall be fixed "
            "securely but not permanently to the packaging and shall describe the items at the most "
            "detailed sorting granularity achieved and name the company responsible for final "
            "sorting. Shipments shall be protected against damage in transport."
        ),
        "criticality": "critical",
        "applicable_entity": "Exporters and shippers of used textiles, sorting operators",
    },
    {
        "article": "Article 22d(6)",
        "requirement_text": (
            "By 1 January 2026, and every five years thereafter, Member States shall carry out a "
            "compositional survey of collected mixed municipal waste to determine the share of waste "
            "textile, textile-related and footwear products, where appropriate by reference to the "
            "Annex IVc CN codes. Competent authorities may require producer responsibility "
            "organisations to take corrective action, including expanding the collection network and "
            "running information campaigns. Results shall be made available to the public."
        ),
        "criticality": "high",
        "applicable_entity": "Member States, competent authorities, PROs",
    },
    {
        "article": "Article 22c(18), (20)",
        "requirement_text": (
            "Producer responsibility organisations shall publish on their websites at least annually, "
            "subject to commercial confidentiality, the quantity by weight of products made "
            "available on the market for the first time; the quantity separately collected, "
            "specifying unsold products separately; the rates of re-use, preparing for re-use and "
            "recycling, specifying fibre-to-fibre recycling separately; the rates of other recovery "
            "and disposal; and the rates of export of products assessed as fit for re-use and of "
            "waste products. The same information shall be provided annually to competent "
            "authorities. Enterprises employing fewer than 10 persons with annual turnover and "
            "balance sheet not exceeding EUR 2 million report only the quantity made available."
        ),
        "criticality": "high",
        "applicable_entity": "PROs, micro-enterprise producers",
    },
    {
        "article": "Article 41 as amended",
        "requirement_text": (
            "From 17 April 2029, Articles 22a, 22b, 22c and 22d apply to enterprises which employ "
            "fewer than 10 persons and whose annual turnover and annual balance sheet do not exceed "
            "EUR 2 million. Until that date micro-enterprises are outside the textile extended "
            "producer responsibility obligations, subject to any pre-existing national scheme "
            "maintained under Article 193 TFEU."
        ),
        "criticality": "medium",
        "applicable_entity": "Micro-enterprise producers of Annex IVc products",
    },
    {
        "article": "Article 9a(4)",
        "requirement_text": (
            "Member States shall take the necessary and appropriate measures to achieve, by "
            "31 December 2030, a reduction of food waste generated in processing and manufacturing "
            "of 10 per cent, and a reduction of food waste per capita generated jointly in retail "
            "and other distribution of food, in restaurants and food services and in households of "
            "30 per cent, in both cases compared with the annual average generated between 2021 and "
            "2023."
        ),
        "criticality": "critical",
        "applicable_entity": "Member States, food processors, retailers, food service",
    },
    {
        "article": "Article 9a(1)",
        "requirement_text": (
            "Member States shall take measures to prevent food waste along the entire food supply "
            "chain including at least: behavioural change interventions and awareness campaigns; "
            "identifying and addressing inefficiencies in the supply chain while ensuring fair "
            "distribution of costs and benefits; encouraging food donation and other redistribution "
            "for human consumption, prioritising human use over animal feed and non-food "
            "reprocessing; supporting training, skills and access to funding particularly for SMEs "
            "and social economy entities; and encouraging innovation and technological solutions. "
            "Member States shall, after consulting food banks, take measures where appropriate so "
            "that operators with a significant role in food waste propose donation agreements at a "
            "reasonable cost."
        ),
        "criticality": "high",
        "applicable_entity": "Member States, food business operators, retailers, food banks",
    },
    {
        "article": "Article 29a",
        "requirement_text": (
            "Member States shall designate the competent authorities responsible for coordinating "
            "food waste prevention measures and inform the Commission by 17 January 2026. Member "
            "States shall evaluate and adapt their food waste prevention programmes with a view to "
            "attaining the Article 9a(4) targets and communicate them to the Commission by "
            "17 October 2027."
        ),
        "criticality": "high",
        "applicable_entity": "Member States, national competent authorities",
    },
    {
        "article": "Article 2(1)",
        "requirement_text": (
            "Member States shall bring into force the laws, regulations and administrative "
            "provisions necessary to comply with this Directive by 17 June 2027 at the latest and "
            "shall immediately inform the Commission. Transposing measures shall contain a reference "
            "to this Directive or be accompanied by such a reference on official publication."
        ),
        "criticality": "critical",
        "applicable_entity": "Member States",
    },
]


def main():
    db = SessionLocal()
    try:
        existing = db.query(LawRequirement).filter(
            LawRequirement.law_id == LAW_ID
        ).count()
        if existing:
            print(f"[SKIP] {existing} requirements already exist for law_id={LAW_ID}")
            return
        for r in REQUIREMENTS:
            db.add(LawRequirement(
                law_id=LAW_ID,
                cluster_id=CLUSTER_ID,
                article=r["article"],
                requirement_text=r["requirement_text"],
                criticality=r["criticality"],
                applicable_entity=r["applicable_entity"],
                extra_metadata={"source": "canon_curated_seed", "seeded_at": "2026-08-05"},
            ))
        db.commit()
        n = db.query(LawRequirement).filter(LawRequirement.law_id == LAW_ID).count()
        print(f"[OK] seeded {n} requirements for Dir (EU) 2025/1892 "
              f"(law_id={LAW_ID}, cluster_id={CLUSTER_ID})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
