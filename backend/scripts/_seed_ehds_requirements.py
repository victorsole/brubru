"""Seed the canonical headline obligations of Reg (EU) 2025/327 (EHDS) into law_requirements.

Pre-curated from a full sequential read of the Regulation (115 recitals, 105 articles, 9 chapters,
4 annexes) - Brubru canon project, 8 July 2026. Pre-seeding guarantees EU Law Comply can produce a
complete compliance report for any in-scope Member State authority, healthcare provider, EHR
system manufacturer, health data holder, health data user or wellness application manufacturer
even when the AI extractor cannot parse the Formex source cleanly.

IDs verified after running create_law_clusters.py --package ehds_european_health_data_space:
  SELECT id, celex FROM eu_laws WHERE celex='32025R0327';                              -> 9327
  SELECT id, name FROM law_clusters WHERE name = 'EHDS - European Health Data Space';  -> 56
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

EHDS_LAW_ID = 9327
EHDS_CLUSTER_ID = 56

REQUIREMENTS = [
    {
        "article": "Article 3",
        "requirement_text": (
            "Every natural person has the right to access personal electronic health data relating "
            "to them that belong to the six priority categories (patient summaries, electronic "
            "prescriptions, electronic dispensations, medical imaging studies and reports, medical "
            "test results, discharge reports). Access must be provided immediately after registration "
            "in an EHR system, free of charge, in an easily readable and consolidated format, and "
            "downloadable as an electronic copy in the European electronic health record exchange "
            "format. Member States may restrict access temporarily on patient-safety grounds "
            "(Regulation (EU) 2016/679, Art 23) until a health professional can properly communicate "
            "information with significant health impact."
        ),
        "criticality": "critical",
        "applicable_entity": "Member States, healthcare providers, EHR system operators",
    },
    {
        "article": "Article 4",
        "requirement_text": (
            "Each Member State must establish one or more electronic health data access services "
            "(national / regional / local) enabling every natural person to exercise rights under "
            "Articles 3 and 5 to 10, free of charge. These services must include proxy services "
            "letting a natural person authorise other natural persons to access their data on their "
            "behalf, and letting legal representatives access data of persons whose affairs they "
            "administer. Proxy services must be interoperable across Member States and accessible "
            "to persons with disabilities, vulnerable groups and persons with low digital literacy."
        ),
        "criticality": "critical",
        "applicable_entity": "Member States (digital health authorities)",
    },
    {
        "article": "Article 7",
        "requirement_text": (
            "Every natural person has the right to data portability: to give access to, or request "
            "a healthcare provider to transmit, all or part of their personal electronic health "
            "data to another healthcare provider of their choice, immediately, free of charge and "
            "without hindrance. Cross-border transmission must take place in the European electronic "
            "health record exchange format via MyHealth@EU. The receiving healthcare provider must "
            "accept and be able to read the data."
        ),
        "criticality": "critical",
        "applicable_entity": "healthcare providers, EHR system manufacturers",
    },
    {
        "article": "Article 9",
        "requirement_text": (
            "Natural persons have the right to obtain information (including through automatic "
            "notifications) on any access to their personal electronic health data through the "
            "health professional access service. Information must be provided free of charge and "
            "without delay via electronic health data access services and must be retained and "
            "available for at least three years from each date of access. It must include the "
            "identity of the healthcare provider or individual who accessed the data, the date "
            "and time of access, and which data were accessed."
        ),
        "criticality": "important",
        "applicable_entity": "healthcare providers, EHR system operators",
    },
    {
        "article": "Article 13",
        "requirement_text": (
            "Healthcare providers processing electronic health data must register at least the "
            "priority categories referred to in Article 14 in electronic format in an EHR system. "
            "Data must be kept updated with information related to the healthcare provided. Where "
            "registration is performed in a Member State of treatment different from the Member "
            "State of affiliation, the identification data of the natural person in the Member "
            "State of affiliation must be used. Each registration or update must identify the "
            "health professional and healthcare provider and the time of registration."
        ),
        "criticality": "critical",
        "applicable_entity": "healthcare providers",
    },
    {
        "article": "Article 14",
        "requirement_text": (
            "For primary use, Member States must ensure the following six priority categories of "
            "personal electronic health data are accessible and exchangeable in electronic format: "
            "(a) patient summaries; (b) electronic prescriptions; (c) electronic dispensations; "
            "(d) medical imaging studies and related imaging reports; (e) medical test results "
            "including laboratory and other diagnostic results and related reports; (f) discharge "
            "reports. The main characteristics of each category are set out in Annex I. Categories "
            "(a), (b), (c) apply from 26 March 2029; categories (d), (e), (f) apply from 26 March "
            "2031."
        ),
        "criticality": "critical",
        "applicable_entity": "Member States, healthcare providers, EHR system manufacturers",
    },
    {
        "article": "Article 19",
        "requirement_text": (
            "Each Member State must designate one or more digital health authorities responsible "
            "for the implementation and enforcement of Chapters II and III at national level, and "
            "must notify the Commission of their identity by 26 March 2027. Where several are "
            "designated, one must be nominated as coordinator. Authorities must be provided with "
            "the human, technical and financial resources, premises and infrastructure necessary "
            "for effective performance of their tasks. They must avoid conflicts of interest and "
            "act in the public interest."
        ),
        "criticality": "critical",
        "applicable_entity": "Member States",
    },
    {
        "article": "Article 23",
        "requirement_text": (
            "Each Member State must designate one national contact point for digital health "
            "(notified to the Commission by 26 March 2027), which becomes an organisational and "
            "technical gateway for cross-border exchange of personal electronic health data. The "
            "national contact point must be connected to all other national contact points and to "
            "the MyHealth@EU central platform. All healthcare providers must be connected to their "
            "national contact point, enabling two-way exchange of electronic health data. All "
            "pharmacies (including online pharmacies) must be able to dispense electronic "
            "prescriptions issued in other Member States and report the dispensation through "
            "MyHealth@EU."
        ),
        "criticality": "critical",
        "applicable_entity": "Member States, healthcare providers, pharmacies",
    },
    {
        "article": "Article 25",
        "requirement_text": (
            "Every EHR system placed on the market or put into service in the Union must include "
            "a European interoperability software component for EHR systems and a European logging "
            "software component for EHR systems (the two harmonised software components), meeting "
            "the essential requirements laid down in Annex II. General-purpose software used in a "
            "healthcare environment is out of scope."
        ),
        "criticality": "critical",
        "applicable_entity": "EHR system manufacturers, distributors and importers",
    },
    {
        "article": "Article 26",
        "requirement_text": (
            "EHR systems may be placed on the market or put into service only if they comply with "
            "Chapter III. EHR systems manufactured and used within Union health institutions and "
            "EHR systems offered as a service (SaaS, per Directive (EU) 2015/1535 Art 1(1)(b)) "
            "are treated as having been put into service. Member States may not restrict placing "
            "on the market of compliant EHR systems on the basis of the harmonised software "
            "components. Chapter III applies to EHR systems put into service in the Union from "
            "26 March 2031."
        ),
        "criticality": "critical",
        "applicable_entity": "EHR system manufacturers, health institutions, SaaS providers",
    },
    {
        "article": "Article 27",
        "requirement_text": (
            "Manufacturers of medical devices (Regulation (EU) 2017/745) and in vitro diagnostic "
            "medical devices (Regulation (EU) 2017/746), and providers of high-risk AI systems "
            "under Regulation (EU) 2024/1689 that do not fall under 2017/745 or 2017/746, that "
            "claim interoperability of their product with the harmonised software components of "
            "EHR systems must prove compliance with the essential requirements on the European "
            "interoperability and logging software components laid down in Section 2 of Annex II. "
            "Common specifications under Article 36 apply."
        ),
        "criticality": "critical",
        "applicable_entity": "medical device manufacturers, in vitro diagnostic manufacturers, high-risk AI providers",
    },
    {
        "article": "Article 36",
        "requirement_text": (
            "EHR systems must meet the essential requirements set out in Annex II. Where the "
            "Commission has adopted common specifications, EHR systems in conformity with them "
            "are presumed to conform with the corresponding essential requirements. Manufacturers "
            "must justify departures and demonstrate that adopted solutions guarantee an equivalent "
            "level."
        ),
        "criticality": "critical",
        "applicable_entity": "EHR system manufacturers",
    },
    {
        "article": "Article 39",
        "requirement_text": (
            "For each EHR system, the manufacturer must draw up an EU declaration of conformity "
            "stating that the essential requirements of Annex II are fulfilled, containing the "
            "information set out in Annex IV. Where the EHR system is subject to other Union legal "
            "acts requiring an EU declaration of conformity, a single declaration covering all "
            "must be drawn up. Where drawn up in digital format, it must remain accessible online "
            "for at least ten years from placing on the market or putting into service."
        ),
        "criticality": "critical",
        "applicable_entity": "EHR system manufacturers",
    },
    {
        "article": "Article 41",
        "requirement_text": (
            "Before placing an EHR system on the market, the manufacturer must affix the CE marking "
            "of conformity visibly, legibly and indelibly to the accompanying documents and, where "
            "applicable, the packaging. The CE marking is subject to the general principles in "
            "Article 30 of Regulation (EC) No 765/2008."
        ),
        "criticality": "critical",
        "applicable_entity": "EHR system manufacturers",
    },
    {
        "article": "Article 47",
        "requirement_text": (
            "Manufacturers of wellness applications that claim interoperability with an EHR system "
            "in relation to the harmonised software components (and therefore compliance with the "
            "common specifications under Article 36 and Annex II essential requirements) must "
            "accompany the application with a label indicating the categories of electronic health "
            "data for which compliance was confirmed, the referenced common specifications and the "
            "validity period. The label maximum validity is three years. Where the wellness "
            "application is only software, the label must be shown in the application in digital "
            "form."
        ),
        "criticality": "important",
        "applicable_entity": "wellness application manufacturers, suppliers, distributors",
    },
    {
        "article": "Article 51",
        "requirement_text": (
            "Health data holders must make the seventeen minimum categories of electronic health "
            "data available for secondary use under Chapter IV, including EHR data, socioeconomic "
            "and behavioural determinants, aggregated healthcare data, pathogen data, administrative "
            "data, human genetic and genomic data, other omics data, medical-device data, wellness "
            "application data, health-professional data, population registries, medical and "
            "mortality registries, clinical trial and study data, medicinal-product and medical-"
            "device registries, research-cohort survey data (after first publication of results), "
            "and biobank data. Categories (b), (f), (g), (m), (p) apply from 26 March 2031."
        ),
        "criticality": "critical",
        "applicable_entity": "health data holders (public authorities, private entities, research bodies, wellness app developers, Union institutions)",
    },
    {
        "article": "Article 53",
        "requirement_text": (
            "Health data access bodies may only grant access to electronic health data for secondary "
            "use for the following purposes: (a) public interest in public or occupational health; "
            "(b) policymaking and regulatory activities to support public sector bodies or Union "
            "institutions; (c) statistics as defined in Regulation (EC) No 223/2009; (d) education "
            "or teaching in health/care sectors at vocational or higher-education level; (e) "
            "scientific research including AI training and evaluation; (f) improvement of care "
            "delivery. Access under (a), (b), (c) is reserved for public sector bodies and Union "
            "institutions."
        ),
        "criticality": "critical",
        "applicable_entity": "health data access bodies, health data users",
    },
    {
        "article": "Article 54",
        "requirement_text": (
            "Health data users must not process electronic health data for: (a) decisions "
            "detrimental to a natural person or group with legal, social or economic effects; "
            "(b) discriminatory decisions on job offers, goods, services, insurance or credit "
            "contracts, premium modification, exclusion; (c) advertising or marketing; (d) "
            "developing harmful products (illicit drugs, alcohol, tobacco, nicotine, weapons, "
            "addiction-inducing products); (e) activities contrary to national ethical provisions."
        ),
        "criticality": "critical",
        "applicable_entity": "health data users",
    },
    {
        "article": "Article 55",
        "requirement_text": (
            "Each Member State must designate one or more health data access bodies responsible "
            "for Articles 57, 58 and 59, notified to the Commission by 26 March 2027. Where "
            "several are designated, one must be nominated as coordinator. Bodies must be "
            "provided with sufficient human, financial and technical resources, expertise, premises "
            "and infrastructure. Ethics-body expertise must be available where required by national "
            "law. Bodies must avoid conflicts of interest, in particular between assessing "
            "applications, preparing datasets and providing data in secure processing environments."
        ),
        "criticality": "critical",
        "applicable_entity": "Member States",
    },
    {
        "article": "Article 60",
        "requirement_text": (
            "Health data holders must make relevant electronic health data available to the health "
            "data access body pursuant to a data permit or approved health data request, within "
            "three months of receipt (extendable by up to three months in justified cases). Health "
            "data holders must communicate to the health data access body a dataset description in "
            "accordance with Article 77, and check it at least annually. Where a data quality and "
            "utility label accompanies the dataset, holders must provide sufficient documentation "
            "for the access body to verify accuracy. Holders of non-personal electronic health "
            "data must provide access through trusted open databases with transparent governance."
        ),
        "criticality": "critical",
        "applicable_entity": "health data holders (excluding natural persons and microenterprises per Art 50)",
    },
    {
        "article": "Article 61",
        "requirement_text": (
            "Health data users may access and process electronic health data for secondary use "
            "only under a data permit, health data request approval or HealthData@EU access "
            "approval. They must not provide access to third parties not mentioned in the data "
            "permit and must not re-identify or attempt to re-identify natural persons. Results "
            "or output must be made public within 18 months of completion of processing (extendable "
            "by the access body). Results must contain only anonymous data. Users must inform the "
            "access body of any significant finding related to the health of a natural person "
            "whose data are in the dataset."
        ),
        "criticality": "critical",
        "applicable_entity": "health data users",
    },
    {
        "article": "Article 64",
        "requirement_text": (
            "Health data access bodies may impose administrative fines for infringements. Lower "
            "tier: up to EUR 10 000 000 or 2 % of total worldwide annual turnover in the preceding "
            "financial year (whichever is higher) for infringements of duties under Article 60 or "
            "Article 61(1), (5), (6). Upper tier: up to EUR 20 000 000 or 4 % of total worldwide "
            "annual turnover (whichever is higher) for processing data for prohibited uses (Art "
            "54), extracting personal electronic health data from secure processing environments, "
            "re-identifying or attempting to re-identify natural persons, or non-compliance with "
            "enforcement measures under Article 63."
        ),
        "criticality": "critical",
        "applicable_entity": "health data users, health data holders, undertakings",
    },
    {
        "article": "Article 71",
        "requirement_text": (
            "Every natural person has the right to opt out at any time, without reason, from the "
            "processing of personal electronic health data relating to them for secondary use. The "
            "right must be reversible. Member States must provide an accessible, easily "
            "understandable opt-out mechanism. Once exercised, the data must not be made available "
            "or processed under new data permits or health data requests. Exceptions are permitted "
            "only for public-interest research or public-health tasks by public sector bodies "
            "where data cannot be obtained by alternative means (Art 71(4))."
        ),
        "criticality": "critical",
        "applicable_entity": "Member States, health data access bodies, health data users",
    },
    {
        "article": "Article 73",
        "requirement_text": (
            "Health data access bodies must provide access to electronic health data pursuant to "
            "data permits only within a secure processing environment that complies with "
            "state-of-the-art data security, confidentiality and protection standards. The "
            "environment must restrict transfer of data not covered by the data permit, log all "
            "processing operations, and verify that health data users do not upload code that "
            "may exfiltrate data. Only anonymised data may be downloaded outside the environment."
        ),
        "criticality": "critical",
        "applicable_entity": "health data access bodies, trusted health data holders",
    },
    {
        "article": "Article 75",
        "requirement_text": (
            "Each Member State must designate one national contact point for secondary use "
            "(notified to the Commission by 26 March 2027) responsible for making electronic "
            "health data available for secondary use in a cross-border context. National contact "
            "points must connect to HealthData@EU, the Union-level cross-border infrastructure "
            "for secondary use. Health-related research infrastructures may become authorised "
            "participants. Third countries and international organisations may become authorised "
            "participants (Art 75(5) from 26 March 2035) subject to compliance decisions by the "
            "Commission."
        ),
        "criticality": "critical",
        "applicable_entity": "Member States, health data access bodies, research infrastructures",
    },
    {
        "article": "Article 78",
        "requirement_text": (
            "Datasets with electronic health data collected and processed with the support of Union "
            "or national public funding must carry a Union data quality and utility label covering "
            "data documentation, technical quality assessment, data quality management processes, "
            "coverage assessment, information on access and provision, and information on data "
            "modifications. The Commission sets the visual characteristics and technical "
            "specifications by implementing act."
        ),
        "criticality": "important",
        "applicable_entity": "health data holders, health data access bodies",
    },
]


def main():
    db = SessionLocal()
    try:
        existing = db.query(LawRequirement).filter(LawRequirement.law_id == EHDS_LAW_ID).count()
        if existing:
            print(f"EHDS already has {existing} requirements seeded - skipping insertion")
            return
        inserted = 0
        for r in REQUIREMENTS:
            req = LawRequirement(
                law_id=EHDS_LAW_ID,
                cluster_id=EHDS_CLUSTER_ID,
                article=r["article"][:50],
                requirement_text=r["requirement_text"],
                criticality=r["criticality"],
                applicable_entity=r["applicable_entity"][:100],
            )
            db.add(req)
            inserted += 1
        db.commit()
        print(f"inserted {inserted} EHDS requirements into law_requirements (law_id={EHDS_LAW_ID}, cluster_id={EHDS_CLUSTER_ID})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
