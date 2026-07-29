"""Seed the canonical headline obligations of Reg (EU) 2025/40 (PPWR) into law_requirements.

Pre-curated from a full sequential read of the Regulation (189 recitals, 71 articles, 13 chapters,
13 annexes) - Brubru canon project, 29 July 2026. Pre-seeding guarantees EU Law Comply can produce a
complete compliance report for any in-scope producer, distributor, waste operator, PRO,
Member-State authority or DRS operator even when the AI extractor cannot parse the Formex source
cleanly.

IDs verified after running create_law_clusters.py --package ppwr_packaging_and_packaging_waste and
_ingest_ppwr_oneshot.py:
  SELECT id, celex FROM eu_laws WHERE celex='32025R0040';                                 -> 23636
  SELECT id, name FROM law_clusters WHERE name = 'PPWR - Packaging and Packaging Waste Regulation'; -> 57
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

PPWR_LAW_ID = 23636
PPWR_CLUSTER_ID = 57

REQUIREMENTS = [
    {
        "article": "Article 5",
        "requirement_text": (
            "Packaging shall be manufactured so that the sum concentration levels of lead, cadmium, "
            "mercury and hexavalent chromium in packaging or packaging components does not exceed "
            "100 mg/kg. For packaging placed on the Union market on or after 12 August 2026, the "
            "presence of per- and polyfluoroalkyl substances (PFAS) in food-contact packaging is "
            "restricted above defined thresholds (25 ppb any single PFAS measured with targeted "
            "analysis; 250 ppb sum of PFAS measured as sum of targeted analysis of PFAS with "
            "optional pre-degradation; 50 ppm PFAS-total; extractable organic fluorine measured as "
            "a proxy). Substances of concern in packaging and packaging components must be "
            "minimised at source in line with REACH (Regulation (EC) No 1907/2006)."
        ),
        "criticality": "critical",
        "applicable_entity": "packaging manufacturers, importers, brand owners of food-contact packaging",
    },
    {
        "article": "Article 6",
        "requirement_text": (
            "From 1 January 2030, all packaging placed on the Union market shall be recyclable. It "
            "is recyclable when it is designed for material recycling and can be effectively and "
            "efficiently separately collected, sorted into defined waste streams without affecting "
            "the recyclability of other waste streams, and recycled so that the resulting secondary "
            "raw materials can substitute primary raw materials. Recyclability shall be assessed "
            "against the design-for-recycling criteria adopted by the Commission (delegated act) "
            "and classified into Grades A, B or C per Annex II Table 3. From 1 January 2038, "
            "packaging in Grade C (< 70 % recyclability performance grade) shall not be placed on "
            "the Union market."
        ),
        "criticality": "critical",
        "applicable_entity": "packaging manufacturers, importers, distributors, brand owners",
    },
    {
        "article": "Article 7",
        "requirement_text": (
            "From 1 January 2030, the plastic part of packaging placed on the Union market shall "
            "contain a minimum percentage of recycled content recovered from post-consumer plastic "
            "waste per packaging type: contact-sensitive packaging made from PET as the major "
            "component 30 %; other contact-sensitive plastic packaging (except PET) 10 %; single-"
            "use plastic beverage bottles 30 %; other plastic packaging 35 %. From 1 January 2040, "
            "targets rise to 50 %, 25 %, 65 % and 65 % respectively. Compostable plastic packaging, "
            "immediate packaging of medicinal products (Directives 2001/82/EC, 2001/83/EC) and "
            "medical devices (Regulations (EU) 2017/745, (EU) 2017/746) are exempt."
        ),
        "criticality": "critical",
        "applicable_entity": "manufacturers, brand owners of plastic packaging",
    },
    {
        "article": "Article 9",
        "requirement_text": (
            "Packaging shall be designed so that its weight and volume is reduced to the minimum "
            "necessary for ensuring its functionality (product protection, safety, hygiene, "
            "acceptability for the consumer, information, transport and end-of-life). Marketing or "
            "consumer-acceptance considerations that increase the weight or volume of the packaging "
            "shall not be considered as packaging function. Double walls, false bottoms and other "
            "characteristics that only increase the perceived product volume are prohibited. "
            "Compliance shall be demonstrated through a technical documentation set out in Annex "
            "VII. Sales packaging that meets Directive 94/62/EC essential requirements before "
            "12 February 2028 is presumed compliant until 12 February 2030."
        ),
        "criticality": "critical",
        "applicable_entity": "manufacturers, brand owners, all packaging placed on the market",
    },
    {
        "article": "Article 10",
        "requirement_text": (
            "Reusable packaging shall be conceived, designed and placed on the market with the "
            "objective of being reused multiple times, and shall meet all of the following: it is "
            "conceived for accomplishing multiple trips or rotations; its constitutive materials, "
            "components and characteristics enable multiple rotations under normally foreseeable "
            "conditions of use; it can be emptied or unloaded without damage that would prevent "
            "further reuse; it can be reconditioned per Annex VI Part A; and it is subject to a "
            "reuse system meeting Annex VI Part B and, where applicable, a system for refill "
            "meeting Annex VI Part C. Compliance is demonstrated in the technical documentation "
            "referred to in Annex VII."
        ),
        "criticality": "critical",
        "applicable_entity": "manufacturers, distributors, operators of reuse/refill systems",
    },
    {
        "article": "Article 12",
        "requirement_text": (
            "From 12 August 2028, packaging placed on the Union market shall carry a harmonised "
            "label indicating its material composition to enable proper sorting by consumers. From "
            "the same date, waste containers used for the separate collection of packaging waste "
            "shall carry matching labels. Reusable packaging shall carry a harmonised reuse label "
            "and a QR code (or equivalent digital data carrier) providing information on its "
            "reusability, refill points and reuse-system contact points. Compostable packaging "
            "must be labelled 'industrially compostable' with the standard EN 13432 marking. "
            "Labels shall be legible and unremovable during normal use. From 1 January 2030, "
            "packaging shall bear a label indicating its recycled-content percentage."
        ),
        "criticality": "critical",
        "applicable_entity": "manufacturers, distributors, brand owners; Member States for collection bin labels",
    },
    {
        "article": "Article 24",
        "requirement_text": (
            "From 1 January 2030, the empty space ratio in grouped packaging, transport packaging "
            "and e-commerce packaging shall be a maximum of 50 %. Empty space is the difference "
            "between the total volume of the packaging and the volume of the sales packaging (or "
            "the total product volume for grouped or transport packaging) contained within. "
            "Air-fillers, cushioning, packaging inserts and other filling materials count towards "
            "the empty-space calculation. Economic operators shall demonstrate compliance through "
            "the technical documentation set out in Annex VII."
        ),
        "criticality": "critical",
        "applicable_entity": "manufacturers, retailers, e-commerce sellers, fulfilment service providers",
    },
    {
        "article": "Article 25",
        "requirement_text": (
            "From 1 January 2030, economic operators shall not place on the Union market packaging "
            "in the formats and for the purposes listed in Annex V. This includes: single-use "
            "plastic grouped packaging (e.g. shrink wrap) for holding together retail multipacks "
            "of beverage cans (with derogations); single-use plastic packaging for fruit and "
            "vegetables in quantities under 1.5 kg (with several exceptions for varieties needing "
            "protection); single-use plastic packaging used and filled at HORECA point for "
            "condiments, sauces, cream, sugar and other individual portions; single-use plastic "
            "packaging for individual portions of accommodation-sector cosmetics/toiletries (e.g. "
            "shampoo, conditioner, body wash, hand cream, hotel amenities) under 100 ml or 100 g; "
            "and very lightweight plastic carrier bags (< 15 microns) except where required for "
            "hygiene or provided as sales packaging for loose food to prevent food wastage."
        ),
        "criticality": "critical",
        "applicable_entity": "manufacturers, HORECA operators, hospitality accommodation providers, retailers, brand owners",
    },
    {
        "article": "Article 26",
        "requirement_text": (
            "From 1 January 2030, final distributors making cold or hot beverages available filled "
            "into a container at the point of sale for takeaway shall offer consumers the "
            "possibility to bring their own container. Final distributors of ready-prepared food "
            "intended for immediate consumption without further preparation, filled into a "
            "container at the point of sale for takeaway, shall likewise offer consumers the "
            "possibility to bring their own container. Final distributors shall ensure that "
            "consumers using their own container are not treated less favourably in terms of price "
            "or product than those using single-use packaging. Final distributors with a sales "
            "area larger than 400 m2 shall dedicate at least 10 % of that area to refill stations "
            "for food and beverages products."
        ),
        "criticality": "high",
        "applicable_entity": "HORECA operators, retailers, food-service final distributors",
    },
    {
        "article": "Article 27",
        "requirement_text": (
            "Final distributors offering distribution of packaged products through e-commerce shall "
            "be considered manufacturers of the packaging in which the goods are dispatched. They "
            "are responsible for ensuring that the e-commerce packaging meets the sustainability "
            "requirements (Chapter II), labelling requirements (Chapter III) and empty-space ratio "
            "(Article 24). Fulfilment service providers (Article 3, point 11 of Regulation (EU) "
            "2019/1020) shall verify that the packaging of goods they store, package, address and "
            "dispatch is compliant with this Regulation and shall not dispatch non-compliant "
            "packaging."
        ),
        "criticality": "high",
        "applicable_entity": "e-commerce marketplaces, online retailers, fulfilment service providers",
    },
    {
        "article": "Article 29",
        "requirement_text": (
            "Economic operators shall meet minimum sector-specific reuse and refill targets by "
            "1 January 2030 (with 2040 uplifts): transport packaging (pallets, crates, boxes, IBCs, "
            "drums, rigid containers used in the supply chain between economic operators or between "
            "distinct sites) 40 % reusable share by 2030 (70 % by 2040); large white goods "
            "(household appliances) 90 % reusable transport packaging by 2030 (100 % by 2040); "
            "grouped transport packaging in the form of pallet wraps, straps and slings 30 % "
            "reusable by 2030 (70 % by 2040); take-away cold or hot beverages 10 % of sales in "
            "reusable format by 2030 (40 % by 2040). Cross-border ambulant operators are exempt. "
            "Member States may set higher national targets."
        ),
        "criticality": "critical",
        "applicable_entity": "distributors, brand owners, HORECA operators, transport-packaging pool operators...",
    },
    {
        "article": "Article 34",
        "requirement_text": (
            "Member States shall take measures to achieve a sustained reduction in the consumption "
            "of lightweight plastic carrier bags (thickness under 50 microns) on their territory. A "
            "sustained reduction is considered to be achieved if the annual consumption does not "
            "exceed 40 lightweight plastic carrier bags per capita by 31 December 2025 and every "
            "subsequent year, or an equivalent target expressed in weight. Member States may "
            "exclude very lightweight plastic carrier bags (thickness under 15 microns) required "
            "for hygiene purposes or provided as sales packaging for loose food to prevent food "
            "wastage. Member States may adopt marketing restrictions on any category of plastic "
            "carrier bag, provided such restrictions are proportionate and non-discriminatory."
        ),
        "criticality": "critical",
        "applicable_entity": "Member States, retailers, distributors of plastic carrier bags",
    },
    {
        "article": "Article 40",
        "requirement_text": (
            "Each Member State shall designate one or more competent authorities responsible for "
            "the application and enforcement of this Regulation. Member States shall notify the "
            "Commission and the other Member States of the identity and contact details of those "
            "competent authorities, and of any subsequent changes. Where more than one competent "
            "authority is designated, Member States shall clearly delimit their tasks and "
            "establish coordination mechanisms. Member States shall ensure that competent "
            "authorities have the powers and resources necessary to fulfil their tasks under this "
            "Regulation."
        ),
        "criticality": "high",
        "applicable_entity": "Member States",
    },
    {
        "article": "Article 43",
        "requirement_text": (
            "Member States shall reduce the packaging waste generated per capita, compared with "
            "the packaging waste generated per capita in 2018, by at least: 5 % by 2030; 10 % by "
            "2035; 15 % by 2040. Member States failing to meet these targets shall take corrective "
            "measures under Article 43(4) and adopt an implementation plan. The Commission shall "
            "publish reports on Member State progress and may issue an early-warning report to "
            "Member States at risk of missing the targets three years before each deadline."
        ),
        "criticality": "critical",
        "applicable_entity": "Member States",
    },
    {
        "article": "Article 44",
        "requirement_text": (
            "Producers of packaged products who make packaging (including service packaging) "
            "available on the territory of a Member State for the first time shall register with "
            "the national producer register maintained by the competent authority of that Member "
            "State before making the packaging available. Registration is a prerequisite for "
            "placing packaging on the market. Producers shall report annually to the register the "
            "quantities and characteristics of packaging placed on the market (by material, weight "
            "and category), and shall pay Extended Producer Responsibility (EPR) financial "
            "contributions modulated by recyclability grade (Article 45). Producers not "
            "established in a Member State but placing packaging on that Member State's market "
            "shall designate an authorised representative for extended producer responsibility."
        ),
        "criticality": "critical",
        "applicable_entity": "producers of packaged products, importers, brand owners; authorised representatives",
    },
    {
        "article": "Article 45",
        "requirement_text": (
            "Member States shall establish and operate Extended Producer Responsibility (EPR) "
            "schemes for all packaging in accordance with the general minimum requirements in "
            "Articles 8 and 8a of Directive 2008/98/EC. EPR financial contributions shall cover "
            "the costs of separate collection, transport, sorting and treatment (including "
            "recycling) of packaging waste, of adequate information provision to end-users about "
            "waste prevention and separate collection, and of data gathering and reporting. "
            "Contributions shall be modulated in a transparent way based on the recyclability "
            "grade of packaging (Article 6) and, where applicable, on the recycled content "
            "(Article 7). Producer Responsibility Organisations (PROs) acting on behalf of "
            "producers shall be authorised by the competent authority and shall meet minimum "
            "operational, financial and transparency requirements."
        ),
        "criticality": "critical",
        "applicable_entity": "Member States, producers, producer responsibility organisations",
    },
    {
        "article": "Article 50",
        "requirement_text": (
            "Member States shall take the necessary measures to ensure the separate collection of "
            "at least 90 % by weight, per calendar year, of single-use plastic beverage bottles "
            "with a capacity of up to 3 litres and single-use metal beverage containers with a "
            "capacity of up to 3 litres placed on the market by 1 January 2029. To meet this target "
            "Member States shall set up Deposit Return Systems (DRS) unless they demonstrate that "
            "the 90 % target has already been reached by the end of 2026 and can be maintained "
            "through alternative measures set out in an implementation plan submitted to the "
            "Commission. Any DRS established shall meet the minimum design requirements in Annex "
            "X (interoperability, deposit collection points at every retail sale point above a "
            "size threshold, deposit value visibility, unclaimed-deposit rules, reporting)."
        ),
        "criticality": "critical",
        "applicable_entity": "Member States, DRS operators, retailers, beverage producers",
    },
    {
        "article": "Article 52",
        "requirement_text": (
            "Member States shall reach the following minimum recycling targets by weight of "
            "packaging waste generated: by 31 December 2025 65 % of all packaging waste and, by "
            "material, plastic 50 %, wood 25 %, ferrous metals 70 %, aluminium 50 %, glass 70 %, "
            "paper and cardboard 75 %; by 31 December 2030 70 % of all packaging waste and, by "
            "material, plastic 55 %, wood 30 %, ferrous metals 80 %, aluminium 60 %, glass 75 %, "
            "paper and cardboard 85 %. Recycling is measured at the point of entry into the "
            "recycling operation per the Commission's harmonised calculation methodology "
            "(Decision (EU) 2019/665). Member States may postpone the 2030 target by up to five "
            "years subject to the conditions in Annex XI."
        ),
        "criticality": "critical",
        "applicable_entity": "Member States, waste-management operators, PROs",
    },
    {
        "article": "Article 63",
        "requirement_text": (
            "By 12 February 2030, the Commission shall adopt implementing acts specifying minimum "
            "mandatory green public procurement (GPP) requirements for public contracts falling "
            "within the scope of Directive 2014/24/EU (public procurement) or Directive 2014/25/EU "
            "(utilities procurement) awarded by contracting authorities or contracting entities in "
            "which the packaging or packaged products represent more than 30 % of the estimated "
            "contract value or of the value of products used by the services that are the object "
            "of the contract. The requirements shall address recyclability, recycled content, "
            "reuse, empty-space ratio and, where relevant, DRS-compatible packaging. Contracting "
            "authorities may derogate on public-security or public-health grounds, or where the "
            "requirements would lead to unresolvable technical difficulties."
        ),
        "criticality": "high",
        "applicable_entity": "contracting authorities, contracting entities, suppliers to the public sector",
    },
    {
        "article": "Article 68",
        "requirement_text": (
            "By 12 February 2027, Member States shall lay down the rules on penalties applicable "
            "to infringements of this Regulation and shall take all measures necessary to ensure "
            "that they are implemented. Penalties shall be effective, proportionate and "
            "dissuasive. Penalties for failure to comply with Articles 24 to 29 (empty space, "
            "restricted formats, reuse, refill, e-commerce, take-away) shall include "
            "administrative fines. Member States shall notify the Commission of the rules and "
            "measures by 12 February 2027 and, without delay, of any subsequent amendment "
            "affecting them."
        ),
        "criticality": "critical",
        "applicable_entity": "Member States, all economic operators subject to Chapter V obligations",
    },
]

def main():
    db = SessionLocal()
    try:
        existing = db.query(LawRequirement).filter(
            LawRequirement.law_id == PPWR_LAW_ID
        ).count()
        if existing:
            print(f"[SKIP] {existing} requirements already exist for law_id={PPWR_LAW_ID}")
            return
        for r in REQUIREMENTS:
            db.add(LawRequirement(
                law_id=PPWR_LAW_ID,
                cluster_id=PPWR_CLUSTER_ID,
                article=r["article"],
                requirement_text=r["requirement_text"],
                criticality=r["criticality"],
                applicable_entity=r["applicable_entity"],
                extra_metadata={"source": "canon_curated_seed", "seeded_at": "2026-07-29"},
            ))
        db.commit()
        n = db.query(LawRequirement).filter(LawRequirement.law_id == PPWR_LAW_ID).count()
        print(f"[OK] seeded {n} requirements for PPWR (law_id={PPWR_LAW_ID}, cluster_id={PPWR_CLUSTER_ID})")
    finally:
        db.close()

if __name__ == "__main__":
    main()
