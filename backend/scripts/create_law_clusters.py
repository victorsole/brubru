"""
Create Curated Law Packages (Clusters)

Automatically identifies and creates clusters for major EU legislative packages:
- GDPR Package (Data Protection)
- DSA/DMA Package (Digital Services/Markets)
- AI Act Package
- Green Deal Package
- Banking Union Package
- And more...

Usage:
    python -m backend.scripts.create_law_clusters
    python -m backend.scripts.create_law_clusters --package gdpr
    python -m backend.scripts.create_law_clusters --dry-run
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw, LawCluster, ClusterLaw
from sqlalchemy import or_


# Major EU Law Packages
LAW_PACKAGES = {
    'gdpr': {
        'name': 'GDPR Package (Data Protection)',
        'primary_celex': '32016R0679',  # GDPR
        'description': 'General Data Protection Regulation and implementing acts covering personal data protection in the EU',
        'applicability': 'Companies processing personal data of EU residents, public authorities, data processors',
        'policy_area': 'Digital Policy and Digital Economy',
        'priority_level': 'high',
        'keywords': ['data protection', 'gdpr', 'personal data', 'privacy', '2016/679'],
        'date_from': 2016
    },

    'dsa': {
        'name': 'Digital Services Act Package',
        'primary_celex': '32022R2065',  # DSA
        'description': 'Digital Services Act regulating online intermediaries and platforms in the EU',
        'applicability': 'Online platforms, intermediary services, very large online platforms (VLOPs)',
        'policy_area': 'Digital Policy and Digital Economy',
        'priority_level': 'high',
        'keywords': ['digital services', 'platform', 'intermediary', '2022/2065', 'online content'],
        'date_from': 2020
    },

    'dma': {
        'name': 'Digital Markets Act Package',
        'primary_celex': '32022R1925',  # DMA
        'description': 'Digital Markets Act establishing rules for digital gatekeepers',
        'applicability': 'Large digital platforms designated as gatekeepers, core platform services',
        'policy_area': 'Digital Policy and Digital Economy',
        'priority_level': 'high',
        'keywords': ['digital markets', 'gatekeeper', '2022/1925', 'core platform services'],
        'date_from': 2020
    },

    'ai_act': {
        'name': 'AI Act Package',
        'primary_celex': '32024R1689',  # AI Act (if indexed)
        'description': 'Artificial Intelligence Act regulating AI systems in the EU',
        'applicability': 'AI system providers, deployers, distributors, importers',
        'policy_area': 'Digital Policy and Digital Economy',
        'priority_level': 'high',
        'keywords': ['artificial intelligence', 'ai system', 'machine learning', 'high-risk ai'],
        'date_from': 2021
    },

    'nis2': {
        'name': 'NIS2 Directive (Cybersecurity)',
        'primary_celex': '32022L2555',  # NIS2
        'description': 'Network and Information Security Directive establishing cybersecurity requirements',
        'applicability': 'Essential and important entities, digital infrastructure operators',
        'policy_area': 'Digital Policy and Digital Economy',
        'priority_level': 'high',
        'keywords': ['cybersecurity', 'network security', 'nis2', '2022/2555', 'cyber threat'],
        'date_from': 2020
    },

    'cbam': {
        'name': 'CBAM Package (Carbon Border Adjustment Mechanism)',
        'primary_celex': '32023R0956',  # CBAM Regulation
        'description': 'Carbon Border Adjustment Mechanism putting an EU-ETS-equivalent carbon price on emissions embedded in imported cement, iron & steel, aluminium, fertilisers, electricity and hydrogen',
        'applicability': 'Importers of CBAM goods (cement, iron & steel, aluminium, fertilisers, electricity, hydrogen), authorised CBAM declarants, indirect customs representatives, third-country installation operators',
        'policy_area': 'Climate Action',
        'priority_level': 'high',
        'keywords': ['cbam', 'carbon border adjustment', '2023/956', 'embedded emissions', 'cbam certificate', 'authorised cbam declarant', 'carbon leakage', 'cbam declaration'],
        'date_from': 2023
    },

    'dora_digital_operational_resilience': {
        'name': 'DORA - Digital Operational Resilience Act',
        'primary_celex': '32022R2554',  # DORA Regulation
        'description': (
            'Regulation (EU) 2022/2554 establishing a harmonised EU-wide framework '
            'for digital operational resilience across the financial sector. Covers '
            'ICT risk management (Chapter II), ICT-related incident reporting (Chapter '
            'III, with three-stage initial/intermediate/final reporting), digital '
            'operational resilience testing including threat-led penetration testing '
            '(TLPT every 3 years) (Chapter IV), management of ICT third-party risk '
            'with mandatory contractual provisions, register of information and exit '
            'strategies (Chapter V Section I), and a Union-level Oversight Framework '
            'for critical ICT third-party service providers run by Lead Overseers from '
            'EBA / ESMA / EIOPA (Chapter V Section II). Applies from 17 January 2025. '
            'Companion Directive (EU) 2022/2556 amends UCITS, Solvency II, AIFMD, CRD '
            'IV, BRRD, MiFID II, PSD2 and IORP II. Lex specialis vs NIS 2 Directive.'
        ),
        'applicability': (
            'Twenty-one categories of financial entity (Art 2): credit institutions, '
            'payment institutions, account information service providers, electronic '
            'money institutions, investment firms, crypto-asset service providers and '
            'issuers of asset-referenced tokens (MiCA), CSDs, CCPs, trading venues, '
            'trade repositories, AIFMs, UCITS management companies, data reporting '
            'service providers, insurance and reinsurance undertakings, insurance / '
            'reinsurance / ancillary insurance intermediaries, IORPs, credit rating '
            'agencies, administrators of critical benchmarks, crowdfunding service '
            'providers, securitisation repositories. Plus ICT third-party service '
            'providers (cloud, software, data-centre, data-analytics) when designated '
            'as critical under Article 31. Carve-outs for small AIFMs, small insurers, '
            'IORPs with at most 15 members, MiFID Art 2/3 exempt persons, microenterprise '
            'insurance intermediaries, post-office giro institutions.'
        ),
        'policy_area': 'Economic and Financial Affairs',
        'priority_level': 'high',
        'keywords': [
            'dora', 'digital operational resilience', 'digital operational resilience act',
            '2022/2554', '32022r2554', '2022/2556', '32022l2556',
            'ict risk management', 'ict risk', 'ict-related incident',
            'major ict-related incident', 'significant cyber threat',
            'tlpt', 'threat-led penetration testing', 'tiber-eu',
            'critical ict third-party service provider', 'ctpp', 'critical tpp',
            'ict third-party risk', 'ict third-party service provider',
            'oversight framework', 'lead overseer', 'oversight forum',
            'joint oversight network', 'jon', 'joint examination team',
            'register of information', 'exit strategy', 'subcontracting',
            'ict concentration risk', 'critical or important function',
            'digital operational resilience strategy', 'business impact analysis', 'bia',
            'ict business continuity policy', 'ict response and recovery plan',
            'cloud computing', 'cloud service provider', 'data centre',
            'cyber threat intelligence', 'information sharing arrangement',
            'cyber-attack', 'cyber resilience', 'cyber hygiene',
            'esa joint committee', 'eba dora', 'esma dora', 'eiopa dora',
            'nis 2', '2022/2555', 'lex specialis',
            'periodic penalty payment', 'oversight fees',
            'financial entity', 'microenterprise',
            'simplified ict risk management framework',
        ],
        'date_from': 2022
    },

    'ehds_european_health_data_space': {
        'name': 'EHDS - European Health Data Space',
        'primary_celex': '32025R0327',  # EHDS Regulation
        'description': (
            'Regulation (EU) 2025/327 establishing the European Health Data Space, '
            'the first sector-specific European data space. Grants natural persons '
            'six substantive rights over their personal electronic health data '
            '(access, insertion, rectification, portability, restriction, information '
            'on access) in six priority categories (patient summaries, e-prescriptions, '
            'e-dispensations, medical imaging, medical test results, discharge '
            'reports). Establishes MyHealth@EU (Chapter II Section 3) for cross-border '
            'primary use and HealthData@EU (Chapter IV Section 4) for cross-border '
            'secondary use. Certifies EHR systems as CE-marked products with two '
            'mandatory harmonised software components (European interoperability + '
            'European logging, Annex II). Sets 17 minimum categories of electronic '
            'health data for secondary use (Art 51) with 6 permitted purposes (Art 53) '
            'and 5 prohibited uses (Art 54). Fines up to EUR 20 000 000 or 4 % of '
            'worldwide turnover for re-identification or extraction from secure '
            'processing environments. Amends Directive 2011/24/EU (Art 14 deleted '
            'from 26 March 2031) and Regulation (EU) 2024/2847 (Cyber Resilience Act). '
            'General application 26 March 2027; secondary use from 26 March 2029; '
            'EHR systems from 26 March 2031; third-country participation from 26 March '
            '2035.'
        ),
        'applicability': (
            'Every EU natural person (rights holder) and every EHR system placed on '
            'the market or put into service in the Union (including systems '
            'manufactured and used within Union health institutions and Software-as-'
            'a-Service EHR systems). All healthcare providers must connect to their '
            'national contact point for digital health. All pharmacies (including '
            'online pharmacies) must be able to dispense electronic prescriptions '
            'issued in other Member States. For secondary use: every health data '
            'holder in the healthcare or care sectors (public authorities, private '
            'entities, wellness application developers, research organisations, '
            'mortality registries, Union institutions) — except natural-person '
            'individual researchers and microenterprises (Art 50 exemption). Health '
            'data users may be natural or legal persons including Union institutions. '
            'Manufacturers of medical devices, in vitro diagnostic medical devices '
            'and high-risk AI systems that claim interoperability with EHR systems '
            'are covered by Chapter III. Wellness applications claiming interoperability '
            'with EHR systems must carry a label (Art 47).'
        ),
        'policy_area': 'Public Health',
        'priority_level': 'high',
        'keywords': [
            'ehds', 'european health data space', 'health data space',
            '2025/327', '32025r0327', 'regulation 2025/327', 'regulation (eu) 2025/327',
            'myhealth@eu', 'myhealth eu', 'healthdata@eu', 'healthdata eu',
            'electronic health record', 'ehr system', 'ehr systems',
            'personal electronic health data', 'electronic health data',
            'primary use of health data', 'secondary use of health data',
            'priority categories of personal electronic health data',
            'patient summary', 'patient summaries',
            'electronic prescription', 'electronic prescriptions',
            'electronic dispensation', 'electronic dispensations',
            'medical imaging study', 'medical test results', 'discharge report',
            'european electronic health record exchange format',
            'european interoperability software component',
            'european logging software component',
            'harmonised software components of ehr systems',
            'digital health authority', 'digital health authorities',
            'health data access body', 'health data access bodies',
            'health data holder', 'health data user', 'health data applicant',
            'data permit', 'health data request', 'health data access application',
            'trusted health data holder', 'secure processing environment',
            'wellness application', 'wellness applications',
            'data quality and utility label', 'dataset catalogue',
            'eu dataset catalogue', 'dataset of high impact for secondary use',
            'ehds board', 'european health data space board',
            'national contact point for digital health',
            'national contact point for secondary use',
            'union health data access service',
            'european digital testing environment',
            'eu database for registration of ehr systems and wellness applications',
            'health professional access service', 'electronic health data access service',
            're-identification', 're-identify',
            'right to opt out primary use', 'right to opt out secondary use',
            'directive 2011/24/eu', 'ehealth network',
            'gdpr', 'data governance act', 'data act', 'ai act',
            'cyber resilience act', 'nis 2', 'medical device regulation', 'ivdr',
            'genetic data', 'genomic data', 'omics data', 'biobank',
            'ce marking ehr', 'declaration of conformity ehr',
        ],
        'date_from': 2025
    },

    'ppwr_packaging_and_packaging_waste': {
        'name': 'PPWR - Packaging and Packaging Waste Regulation',
        'primary_celex': '32025R0040',
        'description': (
            'Regulation (EU) 2025/40 on packaging and packaging waste, amending '
            'Regulation (EU) 2019/1020 and Directive (EU) 2019/904, and repealing '
            'Directive 94/62/EC after 30 years. First EU-wide horizontal packaging '
            'law binding on economic operators (not just Member States) with 13 '
            'Chapters, 71 Articles and 13 Annexes. Sets sustainability requirements '
            'for every packaging placed on the Union market: PFAS ban in food-contact '
            'packaging (from 12 August 2026 + 18 months), lead + cadmium + mercury + '
            'hexavalent chromium sum threshold 100 mg/kg, mandatory recyclability '
            'Grade A/B/C from 1 January 2030 with Grade C losing market access from '
            '1 January 2038, minimum recycled-content targets in plastic packaging '
            'from 2030 and 2040, empty-space ratio ceiling of 50 % for grouped/'
            'transport/e-commerce packaging from 1 January 2030, sector-specific '
            'reuse and refill targets, and Annex V bans on specific single-use '
            'packaging formats (hospitality single-serve sachets, hotel amenities, '
            'fruit and vegetable pre-packs under 1.5 kg, e-commerce shrink wrap). '
            'Mandates Deposit Return Systems reaching 90 % separate collection of '
            'single-use PET beverage bottles and aluminium beverage cans up to 3 L '
            'by 1 January 2029, with a derogation route for Member States already '
            'at 80 % by end 2026. Modernises Extended Producer Responsibility with '
            'fee modulation based on recyclability class. Amends the Single-Use '
            'Plastics Directive (2019/904) to add multi-pack plastic rings to the '
            'SUP ban list. Enters into force 11 February 2025; general application '
            '12 August 2026; penalties framework by 12 February 2027; Commission '
            'evaluation by 12 August 2034.'
        ),
        'applicability': (
            'Every producer placing packaging on the Union market (manufacturer, '
            'importer, distributor, authorised representative, fulfilment service '
            'provider); every final distributor selling packaged products or '
            'offering services using packaging (retailers, wholesalers, HORECA, '
            'e-commerce marketplaces); every waste-management operator handling '
            'packaging waste; every producer responsibility organisation (PRO). '
            'Directly applicable across all Member States without transposition. '
            'Applies regardless of packaging material (plastic, paper, cardboard, '
            'glass, metal, wood, composite, ceramic, textile, biobased) and covers '
            'sales, grouped and transport packaging, including e-commerce shipping '
            'packaging and primary production packaging. Green public procurement '
            'rules (Article 63) bind contracting authorities under Directive '
            '2014/24/EU and Directive 2014/25/EU when packaging exceeds 30 % of '
            'contract value. Market surveillance authorities operate under '
            'Regulation (EU) 2019/1020.'
        ),
        'policy_area': 'Environment',
        'priority_level': 'high',
        'keywords': [
            'ppwr', 'packaging regulation', 'packaging and packaging waste',
            '2025/40', '32025r0040', 'regulation 2025/40', 'regulation (eu) 2025/40',
            'directive 94/62', '94/62/ec', 'packaging directive',
            'single-use plastics', 'sup', 'directive 2019/904', '2019/904',
            'multi-pack plastic rings', 'plastic rings',
            'market surveillance', 'regulation 2019/1020', '2019/1020',
            'sales packaging', 'grouped packaging', 'transport packaging',
            'primary packaging', 'secondary packaging', 'tertiary packaging',
            'service packaging', 'e-commerce packaging',
            'reusable packaging', 'refillable packaging', 'refill',
            'compostable packaging', 'biodegradable packaging',
            'recyclable packaging', 'design for recycling',
            'recyclability grade', 'grade a', 'grade b', 'grade c',
            'recycled content', 'post-consumer plastic', 'pcr',
            'recycled plastic', 'recycled pet',
            'contact-sensitive packaging', 'contact sensitive',
            'empty space ratio', 'empty-space ratio', 'packaging minimisation',
            'excessive packaging', 'over-packaging', 'overpackaging',
            'lightweight plastic carrier bag', 'plastic carrier bag',
            'deposit return system', 'drs', 'deposit refund',
            'pet bottle', 'aluminium beverage can', 'beverage bottle',
            'separate collection', 'collection target',
            'recycling target', 'recycling rate',
            'extended producer responsibility', 'epr', 'eco-modulation',
            'fee modulation', 'producer responsibility organisation', 'pro',
            'circular economy', 'circular economy action plan', 'ceap',
            'waste hierarchy', 'waste framework directive', '2008/98',
            'pfas', 'per- and polyfluoroalkyl',
            'bisphenol a', 'bpa', 'heavy metals in packaging',
            'substances of concern',
            'material identification', 'harmonised label', 'sorting label',
            'annex v', 'annex x', 'annex ii',
            'hospitality', 'horeca', 'take-away',
            'hotel amenities', 'condiment sachet', 'single-serve',
            'fruit and vegetables', 'pre-packed produce',
            'green public procurement', 'gpp',
            'declaration of conformity', 'technical documentation',
            'ecodesign', 'espr', '2024/1781', 'digital product passport',
            'reach', '1907/2006', 'clp', '1272/2008',
            'green deal', 'zero pollution',
        ],
        'date_from': 2025
    },

    'csrd_corporate_sustainability_reporting': {
        'name': 'CSRD - Corporate Sustainability Reporting Directive',
        'primary_celex': '32022L2464',
        'description': (
            'Directive (EU) 2022/2464 amending Directive 2013/34/EU, Directive '
            '2004/109/EC, Directive 2006/43/EC and Regulation (EU) No 537/2014 '
            'as regards corporate sustainability reporting. Replaces the earlier '
            'Non-Financial Reporting Directive 2014/95/EU. Requires large '
            'undertakings, listed SMEs (except micro), and large third-country '
            'undertakings operating in the Union to disclose standardised '
            'sustainability information as a dedicated section of the management '
            'report, prepared under mandatory European Sustainability Reporting '
            'Standards (ESRS) adopted by Commission delegated act, assured by an '
            'independent third party (limited assurance from year 1, potentially '
            'reasonable assurance from 2028), and digitally tagged in ESEF format. '
            'Codifies the double materiality principle: reporting covers both '
            'impacts of the undertaking on people and planet and impacts of '
            'sustainability matters on the undertaking. Content covers business '
            'model + transition plan compatible with 1.5 degrees Celsius / '
            'climate neutrality by 2050, absolute GHG reduction targets for 2030 '
            'and 2050, governance and incentives, due diligence, principal risks, '
            'and indicators covering the whole value chain with a 3-year grace '
            'period. First set of 12 ESRS (2 cross-cutting + 5 environmental + '
            '4 social + 1 governance) adopted by Commission Delegated Regulation '
            '(EU) 2023/2772 on 31 July 2023. Sector-specific ESRS deferred to '
            '30 June 2026. Phased application by wave: Wave 1 (former NFRD PIEs '
            'above 500 employees) FY2024, Wave 2 (all other large undertakings) '
            'FY2025 shifted to FY2027 by Directive (EU) 2025/794, Wave 3 (listed '
            'SMEs) FY2026 shifted to FY2028, Wave 4 (third-country undertakings '
            'with EU turnover above 150 million euros) FY2028. Transposition '
            'deadline 6 July 2024.'
        ),
        'applicability': (
            'Every large undertaking in the Union meeting 2 of 3 thresholds '
            '(balance sheet above 25 million euros, net turnover above 50 million '
            'euros, more than 250 employees); every small or medium-sized '
            'undertaking except micro whose transferable securities are admitted '
            'to trading on an EU regulated market; every parent undertaking of a '
            'large group; every credit institution and insurance undertaking '
            'meeting the size thresholds regardless of legal form; every '
            'third-country undertaking generating more than 150 million euros of '
            'net turnover in the Union in each of the last two consecutive '
            'financial years and having at least one EU subsidiary that is a '
            'large or listed undertaking or one EU branch with net turnover above '
            '40 million euros. Approximately 50,000 undertakings originally, '
            'expected to fall to roughly 7,000 if the substantive Omnibus I '
            'proposal (raising the employee threshold to 1,000) is adopted. '
            'Assurance market open to statutory auditors by default and to '
            'independent assurance services providers where Member States open it. '
            'Enforced by national competent authorities under Directive '
            '2004/109/EC for listed issuers and under national company law for '
            'others; sanctions must be effective, proportionate and dissuasive.'
        ),
        'policy_area': 'Financial Services',
        'priority_level': 'high',
        'keywords': [
            'csrd', 'corporate sustainability reporting directive',
            'corporate sustainability reporting',
            '2022/2464', '32022l2464', 'directive 2022/2464',
            'directive (eu) 2022/2464',
            'nfrd', 'non-financial reporting directive',
            '2014/95', 'directive 2014/95',
            'esrs', 'european sustainability reporting standards',
            '2023/2772', 'delegated regulation 2023/2772',
            'efrag', 'sustainability reporting board',
            'double materiality', 'impact materiality', 'financial materiality',
            'sustainability reporting', 'sustainability disclosure',
            'sustainability statement', 'sustainability report',
            'sustainability assurance', 'assurance of sustainability',
            'limited assurance', 'reasonable assurance',
            'assurance services provider', 'independent assurance',
            'accounting directive', '2013/34', 'directive 2013/34',
            'article 19a', 'article 29a', 'article 29b', 'article 29c',
            'article 29d', 'article 40a',
            'transparency directive', '2004/109', 'directive 2004/109',
            'statutory audit directive', '2006/43', 'directive 2006/43',
            'audit regulation', '537/2014', 'regulation 537/2014',
            'taxonomy regulation', '2020/852', 'regulation 2020/852',
            'sfdr', 'sustainable finance disclosure',
            '2019/2088', 'regulation 2019/2088',
            'transition plan', 'climate transition plan',
            'paris agreement', 'climate neutrality 2050', '1.5 degrees',
            'scope 1', 'scope 2', 'scope 3', 'ghg emissions',
            'greenhouse gas emissions', 'absolute emission reduction',
            'value chain reporting', 'value chain due diligence',
            'sector-specific esrs', 'sector esrs',
            'vsme', 'voluntary sme standard', 'lsme', 'listed sme standard',
            'esef', 'single electronic reporting format',
            'xbrl', 'digital tagging', 'digital taxonomy',
            'omnibus', 'omnibus i', 'omnibus package',
            'stop-the-clock', 'stop the clock', '2025/794',
            'wave 1', 'wave 2', 'wave 3', 'wave 4',
            'esg reporting', 'sustainability information',
            'esrs e1', 'esrs e2', 'esrs e3', 'esrs e4', 'esrs e5',
            'esrs s1', 'esrs s2', 'esrs s3', 'esrs s4', 'esrs g1',
            'sustainability matters',
            'sustainability targets',
        ],
        'date_from': 2022
    },

    'csddd_corporate_sustainability_due_diligence': {
        'name': 'CSDDD - Corporate Sustainability Due Diligence Directive',
        'primary_celex': '32024L1760',
        'description': (
            'Directive (EU) 2024/1760 on corporate sustainability due diligence, '
            'amending Directive (EU) 2019/1937 (Whistleblower Protection) and '
            'Regulation (EU) 2023/2859 (European Single Access Point). Requires '
            'large EU and non-EU companies operating in the Union to identify, '
            'prevent, mitigate, remedy and publicly account for adverse human '
            'rights and environmental impacts across their own operations, their '
            'subsidiaries and their business partners in the chain of activities '
            '(upstream + restricted downstream), and to adopt a climate '
            'transition plan compatible with 1.5 degrees Celsius and 2050 '
            'climate neutrality. Sets an 8-step due diligence process in '
            'Article 5 (integrate, identify + assess, prioritise, prevent + '
            'mitigate, remediate, engage stakeholders, complaints mechanism, '
            'monitor + publicly communicate). Pecuniary penalties capped at no '
            'less than 5 percent of net worldwide turnover (Article 27). '
            'Article 29 civil liability regime with overriding mandatory '
            'application; trade unions and NGOs may bring representative '
            'actions. Phased application by wave: Wave 1 (>5000 employees, '
            '>1.5 billion euros turnover) originally 26 July 2027, postponed to '
            '26 July 2028 by Directive (EU) 2025/794 Stop-the-clock; Wave 2 '
            '(>3000 employees, >900 million euros) 26 July 2029; Wave 3 (all '
            'other in-scope companies) 26 July 2030. Transposition deadline '
            'postponed by one year to 26 July 2027. Substantive Omnibus I '
            'proposal (COM(2025) 81 final, 26 February 2025) still under '
            'negotiation may narrow due diligence to direct suppliers, delete '
            'the civil liability regime and soften the Article 22 climate '
            'transition plan.'
        ),
        'applicability': (
            'EU companies with more than 1,000 employees on average and net '
            'worldwide turnover above 450 million euros; ultimate parent '
            'companies of groups meeting those thresholds on a consolidated '
            'basis; franchising or licensing companies with royalties above '
            '22.5 million euros in the Union and turnover above 80 million '
            'euros; third-country companies with net Union turnover above 450 '
            'million euros in the financial year preceding the last, and their '
            'ultimate parents. Thresholds must be met for two consecutive '
            'financial years. Approximately 6,000 EU companies and 900 non-EU '
            'companies estimated in scope at full roll-out. Pure holding '
            'companies exemptible if a designated Union subsidiary fulfils the '
            'obligations. AIFs and UCITS explicitly excluded. Chain of '
            'activities excludes distribution of dual-use export-controlled '
            'items, weapons, munitions and war materials once export is '
            'authorised, and excludes downstream financial services beyond '
            'direct clients.'
        ),
        'policy_area': 'Financial Services',
        'priority_level': 'high',
        'keywords': [
            'csddd', 'cs3d', 'corporate sustainability due diligence',
            'corporate sustainability due diligence directive',
            '2024/1760', '32024l1760', '32024r1760',
            'directive 2024/1760', 'directive (eu) 2024/1760',
            'human rights due diligence', 'hrdd',
            'environmental due diligence',
            'value chain due diligence', 'chain of activities',
            'business partner', 'upstream business partner', 'downstream business partner',
            'adverse impact', 'adverse human rights impact', 'adverse environmental impact',
            'risk-based due diligence', 'meaningful engagement',
            'prevention and mitigation', 'prevent and mitigate',
            'bringing to an end', 'cease adverse impact',
            'remediation', 'stakeholder engagement',
            'notification mechanism', 'complaints procedure',
            'transition plan', 'climate transition plan',
            'article 22', 'article 27', 'article 29',
            '1.5 degrees celsius', 'paris agreement',
            'climate neutrality 2050',
            'civil liability', 'article 29 civil liability',
            'overriding mandatory application', 'rome ii',
            'representative action', 'ngo representative',
            'trade union standing',
            'pecuniary penalty', 'penalty cap 5 percent',
            'supervisory authority', 'european network of supervisory authorities',
            'authorised representative',
            'substantiated concerns',
            'transposition 26 july 2026', 'transposition 26 july 2027',
            'wave 1 csddd', 'wave 2 csddd', 'wave 3 csddd',
            'omnibus', 'omnibus i', 'stop-the-clock',
            '2025/794', 'directive 2025/794',
            'com(2025) 81', '52025pc0081',
            'lieferkettengesetz', 'loi de vigilance',
            'un guiding principles', 'ohchr ungp',
            'oecd guidelines', 'oecd due diligence guidance',
            'child labour', 'forced labour',
            'nfrd', 'csrd',
            'directive 2013/34', '2013/34',
            'directive 2019/1937', 'whistleblower protection',
            'regulation 2023/2859', 'european single access point',
            'esap',
            'annex human rights',
            'international bill of human rights',
            'ilo core conventions',
        ],
        'date_from': 2024
    },

    'green_deal': {
        'name': 'European Green Deal Package',
        'primary_celex': None,  # Collection of laws, no single primary
        'description': 'Comprehensive package of climate and environmental legislation',
        'applicability': 'All sectors: energy, transport, industry, agriculture',
        'policy_area': 'Climate Action',
        'priority_level': 'high',
        'keywords': ['green deal', 'climate neutral', 'fit for 55', 'emissions reduction', 'renewable energy'],
        'date_from': 2019
    },

    'banking_union': {
        'name': 'Banking Union Package',
        'primary_celex': '32013R1024',  # SSM Regulation
        'description': 'Single Supervisory Mechanism and banking supervision framework',
        'applicability': 'Banks, credit institutions, financial supervisors',
        'policy_area': 'Economic and Financial Affairs',
        'priority_level': 'high',
        'keywords': ['banking union', 'ssm', 'srm', 'prudential supervision', '1024/2013'],
        'date_from': 2012
    },

    'crr_capital_requirements': {
        'name': 'CRR / CRD IV - Bank Prudential Requirements',
        'primary_celex': '32013R0575',  # CRR
        'description': (
            'Capital Requirements Regulation (575/2013) and twin Directive 2013/36/EU (CRD IV) - '
            'the EU Single Rulebook implementation of Basel III for credit institutions and '
            'investment firms. Covers own funds (CET1/AT1/T2), capital ratios (4.5% / 6% / 8%), '
            'credit risk Standardised + IRB approaches, market risk, operational risk, CVA, large '
            'exposures (25% limit), liquidity (LCR 100% / NSFR), leverage ratio (3% binding under '
            'CRR II), Pillar 3 disclosure, and the SME Supporting Factor (0.7619). Amended by CRR '
            'II (Regulation (EU) 2019/876) and CRR III (Regulation (EU) 2024/1623, Basel IV).'
        ),
        'applicability': (
            'EU-authorised credit institutions and investment firms (CRR Article 4(1)(3)); '
            'consolidated supervision of banking groups (CRR Title II of Part One); financial '
            'holding companies and mixed financial holding companies. Investment firms partially '
            'carved out by IFR/IFD (Regulation (EU) 2019/2033 + Directive (EU) 2019/2034).'
        ),
        'policy_area': 'Economic and Financial Affairs',
        'priority_level': 'high',
        'keywords': [
            'crr', 'crd iv', 'capital requirements', 'basel iii', 'basel iv', 'prudential',
            'own funds', 'cet1', 'tier 1', 'tier 2', 'risk-weighted assets', 'rwa',
            'standardised approach', 'irb', 'internal ratings based',
            'large exposures', '25%', 'leverage ratio', 'lcr', 'nsfr',
            'covered bonds', 'sme supporting factor', '0.7619',
            'single rulebook', 'pillar 1', 'pillar 3', '575/2013', '2013/36',
            '32013r0575', '32013l0036', '2019/876', '2024/1623',
            'credit institution', 'investment firm', 'eba', 'ecb', 'ssm',
            'cva', 'counterparty credit risk', 'wrong-way risk',
            'g-sii', 'o-sii', 'capital buffer', 'countercyclical buffer'
        ],
        'date_from': 2013
    },

    'china_bev_countervailing_duties': {
        'name': 'China BEV Countervailing Duties (Reg 2024/2754)',
        'primary_celex': '32024R2754',
        'description': (
            'Commission Implementing Regulation (EU) 2024/2754 imposing definitive '
            'countervailing duties on imports of new battery electric vehicles (BEVs) for '
            'passenger transport originating in the People\'s Republic of China. Adopted '
            '29 October 2024 under Article 15 of the Basic Anti-Subsidy Regulation '
            '(Reg 2016/1037). Definitive additional ad valorem duties: BYD 17.0%, '
            'Geely 18.8%, SAIC 35.3%, Tesla (Shanghai) 7.8%, other cooperating 20.7%, '
            'all other companies 35.3% — on top of the 6.5% conventional MFN tariff. '
            'Central legal finding: threat of material injury (Article 8(8)), not actual '
            'injury — provisional-duty securities released. All 5 undertaking offers '
            'rejected. Default 5-year duration.'
        ),
        'applicability': (
            'EU importers, EU customs authorities, Chinese exporting BEV producers '
            '(BYD/Geely/SAIC/Tesla Shanghai/other cooperating named in Annex/non-cooperating), '
            'EU BEV producers monitoring circumvention, EU automotive industry associations, '
            'Member State competent authorities. Product scope: new fully-electric passenger '
            'BEVs under CN code ex 8703 80 10 / TARIC 8703 80 10 10. Excludes hybrids, '
            'plug-in hybrids, range-extended EVs, and BEVs for goods transport.'
        ),
        'policy_area': 'Trade',
        'priority_level': 'high',
        'keywords': [
            'china bev', 'chinese ev', 'chinese electric vehicle', 'china evs',
            'countervailing duty', 'cvd', 'anti-subsidy', 'anti subsidy',
            'byd', 'geely', 'zeekr', 'saic', 'tesla shanghai', 'maxus',
            'volkswagen china', 'mg motor', 'nio', 'xpeng', 'eevb',
            '8703 80 10', 'taric 8703', 'cn 8703',
            '2024/2754', '32024r2754', '2024/1866', '32024r1866',
            '2024/785', '32024r0785', '2016/1037', '32016r1037',
            'basic anti-subsidy regulation', 'ltar', 'less than adequate remuneration',
            'threat of material injury', 'article 8(8)', 'article 16(2)',
            'price undercutting', 'union interest', 'lesser duty rule',
            'cccme', 'undertaking offer', 'minimum import price', 'mip',
            'facts available', 'article 28', 'sampling', 'individual examination',
            'preferential financing', 'policy banks', 'china development bank',
            'lfp batteries', 'land use rights', 'lur',
            'trade defence', 'foreign subsidies regulation', 'fsr',
        ],
        'date_from': 2024
    },

    'batteries_regulation': {
        'name': 'EU Batteries Regulation (Reg 2023/1542)',
        'primary_celex': '32023R1542',
        'description': (
            'Regulation (EU) 2023/1542 concerning batteries and waste '
            'batteries, repealing Directive 2006/66/EC and amending the Waste '
            'Framework Directive 2008/98/EC and the market surveillance '
            'Regulation (EU) 2019/1020. The first EU law to regulate a product '
            'across its entire life cycle in a single instrument, from '
            'sustainable and responsible sourcing of raw materials through '
            'manufacturing, carbon footprint, performance and durability, '
            'safety, labelling and information, to collection, recycling '
            'efficiency and the recovery of critical raw materials at '
            'end of life. Covers five battery categories: portable, light means '
            'of transport (LMT), starting-lighting-ignition (SLI), industrial '
            'and electric vehicle (EV) batteries. Introduces a mandatory carbon '
            'footprint declaration, minimum recycled-content thresholds for '
            'cobalt, lead, lithium and nickel, supply-chain due diligence '
            'obligations for larger economic operators, removability and '
            'replaceability rules for portable and LMT batteries, and a digital '
            'battery passport with a QR code for LMT, industrial and EV '
            'batteries. Legal bases Article 114 TFEU (internal market) and '
            'Article 192(1) TFEU (environment). Entered into force 17 August '
            '2023; most provisions apply from 18 February 2024, with staggered '
            'dates running to 2036 for the toughest sustainability and '
            'end-of-life targets.'
        ),
        'applicability': (
            'All economic operators placing batteries on the Union market or '
            'putting them into service, regardless of whether the battery is '
            'produced in the Union or imported, sold on its own or incorporated '
            'into appliances, light means of transport, vehicles or other '
            'products. Manufacturers, importers, distributors, authorised '
            'representatives and producers (for extended producer '
            'responsibility) all carry obligations. Supply-chain due diligence '
            'applies to economic operators with net turnover above 40 million '
            'euros (with group and small-and-medium-sized-enterprise carve-'
            'outs). Producer responsibility organisations, waste operators and '
            'recyclers are bound by the collection, treatment and recycling-'
            'efficiency duties.'
        ),
        'policy_area': 'Environment',
        'priority_level': 'high',
        'keywords': [
            'batteries regulation', 'eu batteries regulation',
            'battery regulation', 'batteries and waste batteries',
            '2023/1542', '32023r1542', 'regulation 2023/1542',
            'regulation (eu) 2023/1542',
            'directive 2006/66', '2006/66/ec', '32006l0066',
            'batteries directive', 'waste batteries',
            'portable battery', 'lmt battery', 'light means of transport',
            'sli battery', 'starting lighting ignition',
            'industrial battery', 'electric vehicle battery', 'ev battery',
            'battery passport', 'digital battery passport', 'battery qr code',
            'carbon footprint declaration', 'battery carbon footprint',
            'recycled content', 'recycled cobalt', 'recycled lithium',
            'recycled nickel', 'recycled lead',
            'critical raw materials battery', 'raw material recovery',
            'recycling efficiency', 'material recovery target',
            'collection target batteries', 'collection rate',
            'extended producer responsibility', 'epr battery',
            'producer responsibility organisation',
            'removability', 'replaceability', 'removable battery',
            'battery due diligence', 'supply chain due diligence battery',
            'responsible sourcing', 'cobalt', 'lithium', 'nickel', 'natural graphite',
            'second life battery', 'repurposing', 'state of health',
            'conformity assessment battery', 'ce marking battery',
            'waste framework directive', '2008/98/ec',
            'market surveillance', 'regulation 2019/1020',
            'green deal', 'circular economy', 'battery value chain',
            'strategic action plan on batteries', 'crma battery',
            '2020/0353', 'gigafactory', 'battery recycling',
        ],
        'date_from': 2023
    },

    'espr_ecodesign_regulation': {
        'name': 'ESPR - Ecodesign for Sustainable Products Regulation (Reg 2024/1781)',
        'primary_celex': '32024R1781',
        'description': (
            'Regulation (EU) 2024/1781, the Ecodesign for Sustainable Products '
            'Regulation (ESPR), the framework that lets the Commission set '
            'ecodesign requirements for almost any physical product placed on '
            'the Union market, through product-group delegated acts. It repeals '
            'the old Ecodesign Directive 2009/125/EC, amends Directive (EU) '
            '2020/1828 and Regulation (EU) 2023/1542 (Batteries), and is the act '
            'that creates the EU Digital Product Passport (Articles 9 to 15) and '
            'its central registry. ESPR sets both performance requirements '
            '(durability, reusability, reparability, recycled content, energy '
            'and resource efficiency, presence of substances of concern) and '
            'information requirements carried by the digital product passport. '
            'It also bans the destruction of unsold consumer products (Article '
            '25) starting with textiles and footwear, with derogations and '
            'disclosure duties, mandates a working plan of prioritised product '
            'groups (Article 18: iron and steel, aluminium, textiles including '
            'apparel and footwear, furniture, tyres and more), and provides for '
            'green public procurement requirements, self-regulation measures and '
            'SME support. Legal base Article 114 TFEU. Adopted 13 June 2024, '
            'entered into force 18 July 2024.'
        ),
        'applicability': (
            'Manufacturers, importers, distributors, authorised representatives '
            'and fulfilment service providers placing products in scope on the '
            'Union market, plus online marketplaces and providers of online '
            'search. Concrete obligations bite product-group by product-group as '
            'the Commission adopts delegated acts under Article 4, so a given '
            'operator is bound once a delegated act covers its product. The '
            'unsold-goods destruction ban applies first to large enterprises for '
            'textiles and footwear, with medium enterprises phased in later and '
            'micro and small enterprises largely exempt.'
        ),
        'policy_area': 'Environment',
        'priority_level': 'high',
        'keywords': [
            'espr', 'ecodesign', 'ecodesign regulation',
            'ecodesign for sustainable products', 'sustainable products',
            '2024/1781', '32024r1781', 'regulation 2024/1781',
            'regulation (eu) 2024/1781',
            'ecodesign directive', '2009/125', '32009l0125',
            'digital product passport', 'dpp', 'product passport',
            'delegated act ecodesign', 'working plan', 'product group',
            'performance requirement', 'information requirement',
            'durability', 'reparability', 'reusability', 'recyclability',
            'recycled content', 'resource efficiency', 'energy efficiency',
            'substances of concern', 'destruction of unsold products',
            'unsold consumer products', 'unsold goods ban', 'article 25 espr',
            'green public procurement', 'gpp', 'self-regulation measure',
            'ecodesign requirements', 'circular economy', 'green deal',
            'circular economy action plan', 'article 18 working plan',
            'iron and steel', 'aluminium', 'textiles', 'furniture', 'tyres',
            'online marketplace', 'market surveillance', '2022/0095',
            'battery regulation espr', 'espr delegated act',
        ],
        'date_from': 2024
    },

    'china_egypt_gff_countervailing_duties': {
        'name': 'China and Egypt GFF Countervailing Duties (Reg 2020/776)',
        'primary_celex': '32020R0776',
        'description': (
            'Commission Implementing Regulation (EU) 2020/776 imposing definitive '
            'countervailing duties on imports of certain woven and/or stitched glass '
            'fibre fabrics (GFF) originating in the People\'s Republic of China and '
            'Egypt. Adopted 12 June 2020 under Articles 15 and 24(1) of the Basic '
            'Anti-Subsidy Regulation (Reg 2016/1037). Investigation initiated 16 May '
            '2019 on a complaint by Tech-Fab Europe representing more than 25 % of '
            'Union production. Definitive duties: PRC Jushi Group / Zhejiang Hengshi '
            '/ Taishan Fiberglass 30.7 %, PGTEX China / Chongqing Tenways 17.0 %, '
            'other PRC co-operating in both AS and AD 24.8 %, other PRC co-operating '
            'in AD only 30.7 %, all other PRC companies 30.7 %, Jushi Egypt / Hengshi '
            'Egypt 10.9 %, all other Egyptian companies 10.9 %. The regulation also '
            'amends Reg (EU) 2020/492 (the parallel anti-dumping regulation on the '
            'same product) and discontinues import registration established under '
            'Reg (EU) 2020/44.'
        ),
        'applicability': (
            'EU importers of woven and stitched glass fibre fabrics, EU customs '
            'authorities, Chinese exporting GFF producers (Jushi Group / Zhejiang '
            'Hengshi / Taishan Fiberglass / PGTEX China / Chongqing Tenways and '
            'other co-operating named in Annex I-II), Egyptian exporting GFF '
            'producers (Jushi Egypt, Hengshi Egypt), EU GFF producers and the '
            'European GFF industry association (Tech-Fab Europe), wind-turbine blade '
            'manufacturers and other downstream GFF users in the Union. Product '
            'scope: woven and/or stitched continuous filament glass fibre rovings '
            'and/or yarns under CN ex 70193900 / ex 70194000 / ex 70195900 / ex '
            '70199000 (TARIC 7019390080 / 7019400080 / 7019590080 / 7019900080), '
            'excluding pre-impregnated products and open-mesh fabrics with cell '
            'size > 1.8 mm in both length and width weighing > 35 g/m^2.'
        ),
        'policy_area': 'Trade',
        'priority_level': 'medium',
        'keywords': [
            'glass fibre fabrics', 'gff', 'woven glass fibre', 'stitched glass fibre',
            'countervailing duty', 'cvd', 'anti-subsidy', 'anti subsidy',
            'jushi', 'jushi group', 'jushi egypt', 'hengshi', 'taishan fiberglass',
            'cnbm', 'china jushi', 'sinoma', 'pgtex', 'chongqing tenways',
            '70193900', '70194000', '70195900', '70199000',
            'taric 7019', 'cn 7019',
            '2020/776', '32020r0776', '2020/492', '32020r0492',
            '2020/44', '32020r0044', '2016/1037', '32016r1037',
            'basic anti-subsidy regulation', 'tech-fab europe',
            'setc-zone', 'sino-egyptian cooperation', 'suez',
            'preferential lending', 'preferential financing', 'policy banks',
            'export credits', 'land use rights', 'lur', 'ltar',
            'less than adequate remuneration', 'grants', 'tax preferences',
            'transhipment subsidies', 'cross-border subsidies',
            'wind turbine blades', 'composite materials',
        ],
        'date_from': 2020
    },

    'india_indonesia_sscr_countervailing_duties': {
        'name': 'India and Indonesia Stainless Steel Countervailing Duties (Reg 2022/433)',
        'primary_celex': '32022R0433',
        'description': (
            'Commission Implementing Regulation (EU) 2022/433 imposing definitive '
            'countervailing duties on imports of stainless steel cold-rolled flat '
            'products (SSCR) originating in India and Indonesia. Adopted 15 March '
            '2022 under Articles 15 and 24(1) of the Basic Anti-Subsidy Regulation '
            '(Reg 2016/1037). Investigation initiated 17 February 2021 on a complaint '
            'by EUROFER. Definitive countervailing duties: India Jindal Stainless / '
            'Jindal Stainless Hisar 4.3 %, Chromeni Steels and all other Indian 7.5 %; '
            'Indonesia IRNC Group 21.4 %, Jindal Stainless Indonesia 0 % (de minimis), '
            'non-sampled cooperating 13.5 %, all other Indonesian 20.5 %. Combined '
            'CVD + anti-dumping reaches 42.8 % (Chromeni). The dominant Indonesian '
            'subsidy was nickel ore for less than adequate remuneration, supported by '
            'cross-border Chinese financing channelled through the Morowali Industrial '
            'Park and attributed to the Government of Indonesia (the GFF doctrine). The '
            'regulation also amends Reg (EU) 2021/2012 (the parallel anti-dumping '
            'regulation on the same product).'
        ),
        'applicability': (
            'EU importers of stainless steel cold-rolled flat products, EU customs '
            'authorities, Indian exporting producers (Jindal Group, Chromeni Steels), '
            'Indonesian exporting producers (IRNC Group / Tsingshan-linked, Jindal '
            'Stainless Indonesia), EU stainless steel producers and EUROFER, downstream '
            'SSCR users in automotive, white goods, construction and process industries. '
            'Product scope: flat-rolled stainless steel, not further worked than '
            'cold-rolled, under 19 CN codes in headings 7219 and 7220.'
        ),
        'policy_area': 'Trade',
        'priority_level': 'medium',
        'keywords': [
            'stainless steel cold-rolled flat products', 'sscr', 'stainless steel',
            'cold-rolled flat products', 'countervailing duty', 'cvd',
            'anti-subsidy', 'anti subsidy', 'india indonesia', 'eurofer',
            'jindal', 'jindal stainless', 'jindal stainless hisar',
            'jindal stainless indonesia', 'chromeni', 'chromeni steels',
            'irnc', 'indonesia ruipu nickel', 'tsingshan',
            'morowali', 'morowali industrial park', 'imip',
            'nickel ore', 'nickel ore export ban', '2009 mining law',
            'chromium ore', 'ltar', 'less than adequate remuneration',
            'aas', 'dds', 'epcgs', 'meis', 'duty drawback scheme',
            'advanced authorisation scheme', 'merchandise export from india',
            'china-asean investment cooperation fund', 'caf', 'going out policy',
            'cross-border subsidies', 'bilateral cooperation', 'china indonesia',
            '7219', '7220', 'cn 7219', 'cn 7220', 'taric c654', 'taric c657',
            '2022/433', '32022r0433', '2021/2012', '32021r2012',
            '2016/1037', '32016r1037', 'basic anti-subsidy regulation',
            'double counting', 'article 24(1)', 'de minimis',
            'steel safeguard', '2019/159', 'lesser duty rule',
            'preferential financing', 'policy banks',
        ],
        'date_from': 2022
    },

    'esas_review_regulation': {
        'name': 'ESAs Review (Reg 2019/2175)',
        'primary_celex': '32019R2175',
        'description': (
            'Regulation (EU) 2019/2175 (the ESAs Review) reforming the three European '
            'Supervisory Authorities (EBA, EIOPA, ESMA) and amending MiFIR (Reg 600/2014), '
            'the Benchmarks Regulation (Reg 2016/1011) and the transfer-of-funds regulation '
            '(Reg 2015/847). Adopted 18 December 2019 under Article 114 TFEU. Headline '
            'change: EBA becomes the EU AML/CFT hub for the entire financial sector (central '
            'AML database, internal AML committee, power to request national investigations). '
            'New supervisory-convergence tools across all three ESAs: Union strategic '
            'supervisory priorities (Art 29a), strengthened peer reviews (Art 30), public '
            'Q&A tool (Art 16b), no-action letters (Art 9c), whistleblower protection '
            '(Art 17a), coordination groups (Art 45b). ESMA gains direct supervision of data '
            'reporting services providers and critical benchmarks from 1 Jan 2022. '
            'Application waves: Articles 1/2/3/6 from 1 Jan 2020, Articles 4/5 from 1 Jan 2022.'
        ),
        'applicability': (
            'The three European Supervisory Authorities (EBA, EIOPA, ESMA), national '
            'competent authorities supervising banks, insurers, pension funds and securities '
            'markets, financial sector operators subject to AML/CFT supervision, data '
            'reporting services providers (APAs, CTPs, ARMs), benchmark administrators '
            '(including third-country administrators seeking EU recognition), and EU '
            'financial institutions monitoring supervisory-convergence and equivalence '
            'developments. Amends Reg 1093/2010, 1094/2010, 1095/2010, 600/2014, 2016/1011 '
            'and 2015/847.'
        ),
        'policy_area': 'Economic and Financial Affairs',
        'priority_level': 'medium',
        'keywords': [
            'esas review', 'esas review regulation', 'european supervisory authorities',
            'eba', 'eiopa', 'esma', 'european banking authority',
            'european securities and markets authority', 'esfs', 'esrb',
            'de larosiere', 'founding regulations', 'single rulebook',
            'supervisory convergence', 'union strategic supervisory priorities',
            'peer review', 'peer review committee', 'no action letter',
            'questions and answers', 'whistleblower', 'reporting persons',
            'fitness and propriety', 'coordination groups', 'third-country equivalence',
            'anti-money laundering', 'aml', 'cft', 'countering terrorist financing',
            'central aml database', 'aml committee', 'article 9a', 'article 9b',
            'data reporting services providers', 'apa', 'ctp', 'arm', 'consolidated tape',
            'critical benchmarks', 'benchmark administrators', 'mifir',
            'sustainable finance', 'esg risks', 'fintech',
            '2019/2175', '32019r2175', '1093/2010', '1094/2010', '1095/2010',
            '600/2014', '2016/1011', '2015/847', 'article 114 tfeu',
            'capital markets union', 'amla', 'board of supervisors', 'management board',
        ],
        'date_from': 2019
    },

    'animal_health_law_regulation': {
        'name': 'Animal Health Law (Reg 2016/429)',
        'primary_celex': '32016R0429',
        'description': (
            'Regulation (EU) 2016/429 (the Animal Health Law) is the single EU framework '
            'regulation for transmissible animal diseases. Adopted 9 March 2016 under Articles '
            '43(2), 114 and 168(4)(b) TFEU; entered into force 20 April 2016; applies from 21 '
            'April 2021. It replaced around 40 prior acts. It names five diseases directly '
            '(foot-and-mouth, classical swine fever, African swine fever, highly pathogenic '
            'avian influenza, African horse sickness), sorts listed diseases into five '
            'management categories (A immediate eradication, B compulsory eradication, C '
            'optional eradication, D movement restrictions, E surveillance), and covers '
            'responsibilities and biosecurity, notification and surveillance, eradication '
            'programmes, disease-free status, contingency plans and vaccine banks, disease '
            'control measures and restricted zones, registration and approval of '
            'establishments, identification and traceability, movements within the Union and '
            'TRACES certification, entry from third countries, non-commercial pet movements '
            '(max five pets, EU pet passport), and emergency measures.'
        ),
        'applicability': (
            'Livestock and aquaculture operators, transporters, assembly operators, germinal '
            'product establishments, hatcheries, veterinarians and aquatic animal health '
            'professionals, pet keepers and travellers with pets, importers of animals and '
            'products of animal origin, Member State competent veterinary authorities, '
            'reference laboratories, and the wider food chain. Covers kept and wild animals, '
            'germinal products, products of animal origin, and animal by-products.'
        ),
        'policy_area': 'Food Safety',
        'priority_level': 'medium',
        'keywords': [
            'animal health law', 'ahl', 'transmissible animal diseases', 'animal health',
            'listed diseases', 'disease categorisation', 'category a b c d e',
            'foot and mouth disease', 'classical swine fever', 'african swine fever',
            'avian influenza', 'bird flu', 'african horse sickness', 'brucellosis',
            'zoonoses', 'antimicrobial resistance', 'one health', 'biosecurity',
            'sps agreement', 'oie', 'woah', 'efsa', 'reference laboratories',
            'disease notification', 'adis', 'surveillance', 'eradication programme',
            'disease-free status', 'zones', 'compartments', 'compartmentalisation',
            'contingency plans', 'vaccine bank', 'antigen bank', 'restricted zone',
            'emergency vaccination', 'registration of establishments',
            'approval of establishments', 'confined establishment', 'assembly operation',
            'traceability', 'identification and registration', 'equine passport',
            'germinal products', 'animal health certificate', 'official veterinarian',
            'traces', 'entry into the union', 'third country listing', 'export',
            'pet movements', 'non-commercial movement', 'pet passport', 'rabies vaccination',
            'emergency measures', 'scopaff', 'animal health package',
            '2016/429', '32016r0429', '64/432/eec', '2006/88/ec', '21/2004', '576/2013',
            '21 april 2021', 'food safety', 'veterinary',
        ],
        'date_from': 2016
    },

    'mica_crypto_assets_regulation': {
        'name': 'MiCA (Reg 2023/1114)',
        'primary_celex': '32023R1114',
        'description': (
            'Regulation (EU) 2023/1114 (MiCA, Markets in Crypto-Assets) is the EU first '
            'comprehensive framework for crypto-assets not already regulated as financial '
            'instruments. Adopted 31 May 2023 under Article 114 TFEU; applies from 30 December '
            '2024, with the stablecoin Titles III and IV (asset-referenced tokens and e-money '
            'tokens) from 30 June 2024. It classifies crypto-assets into three types (e-money '
            'tokens, asset-referenced tokens, and other/utility tokens), requires a crypto-'
            'asset white paper, licenses crypto-asset service providers (CASPs) across ten '
            'services with EU-wide passporting, imposes reserve, redemption and own-funds '
            'rules on stablecoin issuers, prohibits crypto market abuse, and gives EBA direct '
            'supervision of significant tokens and ESMA a public register. Also amends the '
            'EBA and ESMA regulations, the CRD and the Whistleblower Directive.'
        ),
        'applicability': (
            'Crypto-asset issuers, offerors and persons seeking admission to trading; '
            'stablecoin issuers (asset-referenced and e-money tokens); crypto-asset service '
            'providers (exchanges, custodians, brokers, trading platforms, advisers, portfolio '
            'managers); credit institutions and electronic money institutions issuing tokens; '
            'national competent authorities, EBA and ESMA; and retail and professional holders '
            'of crypto-assets in the Union.'
        ),
        'policy_area': 'Economic and Financial Affairs',
        'priority_level': 'high',
        'keywords': [
            'mica', 'markets in crypto-assets', 'crypto-assets', 'crypto asset', 'stablecoin',
            'e-money token', 'emt', 'asset-referenced token', 'art', 'utility token',
            'crypto-asset white paper', 'white paper', 'crypto-asset service provider', 'casp',
            'crypto exchange', 'crypto custody', 'trading platform', 'distributed ledger',
            'dlt', 'blockchain', 'consensus mechanism', 'nft', 'non-fungible token',
            'significant token', 'reserve of assets', 'right of redemption', 'own funds',
            'qualifying holding', 'market abuse crypto', 'insider dealing', 'passporting',
            'grandfathering', 'transitional regime', 'eba supervision', 'esma register',
            'monetary sovereignty', 'algorithmic stablecoin', 'credit institution',
            'electronic money institution', 'dora', 'dlt pilot regime',
            '2023/1114', '32023r1114', 'article 114 tfeu', '30 december 2024', '30 june 2024',
            '1 july 2026', 'amends 1093/2010', 'amends 1095/2010', 'amends 2013/36',
        ],
        'date_from': 2023
    },

    'capital_markets_union': {
        'name': 'Capital Markets Union Package',
        'primary_celex': None,
        'description': 'Framework for integrated EU capital markets',
        'applicability': 'Investment firms, fund managers, securities markets',
        'policy_area': 'Economic and Financial Affairs',
        'priority_level': 'high',
        'keywords': ['capital markets union', 'mifid', 'prospectus', 'securities'],
        'date_from': 2015
    },

    'circular_economy': {
        'name': 'Circular Economy Package',
        'primary_celex': None,
        'description': 'Waste reduction, recycling, and circular economy legislation',
        'applicability': 'Manufacturers, waste management, product design',
        'policy_area': 'Environment',
        'priority_level': 'medium',
        'keywords': ['circular economy', 'waste', 'recycling', 'ecodesign', 'sustainable product'],
        'date_from': 2015
    },

    'farm_to_fork': {
        'name': 'Farm to Fork Strategy Package',
        'primary_celex': None,
        'description': 'Sustainable food system legislation',
        'applicability': 'Food producers, distributors, agricultural sector',
        'policy_area': 'Agriculture',
        'priority_level': 'medium',
        'keywords': ['farm to fork', 'sustainable food', 'pesticide reduction', 'organic farming'],
        'date_from': 2020
    },

    'migration_pact': {
        'name': 'Migration and Asylum Pact',
        'primary_celex': None,
        'description': 'Comprehensive migration and asylum framework',
        'applicability': 'Member states, border agencies, asylum authorities',
        'policy_area': 'Migration and Home Affairs',
        'priority_level': 'high',
        'keywords': ['migration', 'asylum', 'border', 'schengen', 'refugee'],
        'date_from': 2020
    },

    # =========================================================================
    # STARTUP-FOCUSED COMPLIANCE PACKAGES (LEG_2025-11)
    # =========================================================================

    'fintech_startup': {
        'name': 'FinTech Startup Compliance',
        'primary_celex': '32015L2366',  # PSD2 (Payment Services Directive 2)
        'description': 'Essential compliance package for FinTech startups: payment services, e-money, crypto-assets, and data protection',
        'applicability': 'FinTech startups, payment service providers, crypto exchanges, digital wallets, neobanks',
        'policy_area': 'Economic and Financial Affairs',
        'priority_level': 'high',
        'keywords': ['payment services', 'psd2', 'e-money', 'mica', 'crypto-asset', 'digital finance', 'open banking', 'strong customer authentication'],
        'date_from': 2015,
        'startup_focused': True,
        'affordability': 'Essential for startups seeking payment licenses or handling transactions'
    },

    'healthtech_startup': {
        'name': 'HealthTech Startup Compliance',
        'primary_celex': '32017R0745',  # MDR (Medical Device Regulation)
        'description': 'Medical device and health data compliance for HealthTech startups',
        'applicability': 'HealthTech startups, medical device manufacturers, digital health apps, telemedicine platforms',
        'policy_area': 'Health',
        'priority_level': 'high',
        'keywords': ['medical device', 'mdr', 'ivdr', 'in vitro diagnostic', 'health data', 'clinical trial', 'ce marking', 'medical app'],
        'date_from': 2017,
        'startup_focused': True,
        'affordability': 'Critical for market access - avoid costly regulatory mistakes'
    },

    'mobility_startup': {
        'name': 'Mobility & Transport Startup Compliance',
        'primary_celex': '32014L0094',  # Alternative Fuels Infrastructure Directive
        'description': 'Compliance for mobility startups: alternative fuels, autonomous vehicles, shared mobility',
        'applicability': 'Mobility startups, EV charging networks, micromobility, autonomous vehicle developers, ride-sharing platforms',
        'policy_area': 'Transport',
        'priority_level': 'high',
        'keywords': ['alternative fuel', 'electric vehicle', 'charging infrastructure', 'autonomous vehicle', 'mobility service', 'type approval', 'vehicle homologation'],
        'date_from': 2014,
        'startup_focused': True,
        'affordability': 'Navigate complex transport regulations before costly prototyping'
    },

    'climate_startup': {
        'name': 'Climate Tech Startup Compliance',
        'primary_celex': '32003L0087',  # EU ETS Directive
        'description': 'Carbon markets, emissions trading, and CBAM compliance for climate startups',
        'applicability': 'Climate tech startups, carbon credit platforms, emission reduction technology, green hydrogen, CCUS',
        'policy_area': 'Climate Action',
        'priority_level': 'high',
        'keywords': ['emissions trading', 'ets', 'carbon border adjustment', 'cbam', 'carbon credit', 'emission allowance', 'carbon pricing', 'climate neutral'],
        'date_from': 2003,
        'startup_focused': True,
        'affordability': 'Understand carbon markets and avoid CBAM penalties'
    },

    'cleantech_startup': {
        'name': 'CleanTech Startup Funding & Compliance',
        'primary_celex': '32021R1119',  # European Climate Law
        'description': 'Green Deal compliance and funding opportunities for CleanTech startups',
        'applicability': 'CleanTech startups, renewable energy, energy efficiency, green hydrogen, sustainable materials',
        'policy_area': 'Climate Action',
        'priority_level': 'high',
        'keywords': ['renewable energy', 'energy efficiency', 'green hydrogen', 'clean technology', 'innovation fund', 'just transition', 'renewable energy directive'],
        'date_from': 2019,
        'startup_focused': True,
        'affordability': 'Identify Green Deal funding + ensure compliance with energy regulations'
    },

    'ai_ml_startup': {
        'name': 'AI/ML Startup Compliance',
        'primary_celex': '32024R1689',  # AI Act
        'description': 'AI Act compliance for machine learning startups and AI system providers',
        'applicability': 'AI/ML startups, algorithm developers, predictive analytics, computer vision, NLP, generative AI',
        'policy_area': 'Digital Policy and Digital Economy',
        'priority_level': 'high',
        'keywords': ['artificial intelligence', 'ai act', 'high-risk ai', 'machine learning', 'foundation model', 'general purpose ai', 'ai system', 'algorithmic transparency'],
        'date_from': 2021,
        'startup_focused': True,
        'affordability': 'Navigate AI Act before product launch - avoid €35M penalties'
    },

    'ecommerce_startup': {
        'name': 'E-commerce & Platform Startup Compliance',
        'primary_celex': '32022R2065',  # DSA
        'description': 'Essential compliance for e-commerce platforms, marketplaces, and online services',
        'applicability': 'E-commerce startups, online marketplaces, platform economy, SaaS providers',
        'policy_area': 'Digital Policy and Digital Economy',
        'priority_level': 'high',
        'keywords': ['digital services', 'e-commerce', 'marketplace', 'consumer protection', 'distance selling', 'online platform', 'intermediary service'],
        'date_from': 2020,
        'startup_focused': True,
        'affordability': 'Avoid DSA content moderation fines + consumer protection disputes'
    },

    'circular_economy_startup': {
        'name': 'Circular Economy Startup Compliance (EPR)',
        'primary_celex': '32008L0098',  # Waste Framework Directive
        'description': 'Extended Producer Responsibility (EPR) and circular economy compliance',
        'applicability': 'Circular economy startups, product-as-service, reuse platforms, waste management, packaging producers',
        'policy_area': 'Environment',
        'priority_level': 'medium',
        'keywords': ['extended producer responsibility', 'epr', 'packaging waste', 'circular economy', 'waste management', 'recycling', 'eco-design', 'right to repair'],
        'date_from': 2008,
        'startup_focused': True,
        'affordability': 'Understand EPR obligations before scaling across EU markets'
    },

    'food_agtech_startup': {
        'name': 'Food & AgTech Startup Compliance',
        'primary_celex': '32002R0178',  # General Food Law
        'description': 'Food safety, novel foods, and agricultural technology compliance',
        'applicability': 'FoodTech startups, AgTech innovators, alternative proteins, vertical farming, food delivery platforms',
        'policy_area': 'Food Safety',
        'priority_level': 'high',
        'keywords': ['food safety', 'novel food', 'food contact material', 'agricultural technology', 'plant protection', 'food labeling', 'traceability'],
        'date_from': 2002,
        'startup_focused': True,
        'affordability': 'Navigate complex food regulations and novel food approvals'
    },

    'saas_b2b_startup': {
        'name': 'SaaS & B2B Startup Compliance',
        'primary_celex': '32016R0679',  # GDPR
        'description': 'Data protection, security, and B2B software compliance essentials',
        'applicability': 'SaaS startups, B2B software, cloud services, enterprise software, data processors',
        'policy_area': 'Digital Policy and Digital Economy',
        'priority_level': 'high',
        'keywords': ['gdpr', 'data protection', 'cloud computing', 'data processor', 'data processing agreement', 'cybersecurity', 'nis2'],
        'date_from': 2016,
        'startup_focused': True,
        'affordability': 'Essential GDPR + NIS2 compliance without expensive DPO hiring'
    },

    'textile_epr': {
        'name': 'Textile EPR and Food Waste Package',
        'primary_celex': '32025L1892',  # Dir (EU) 2025/1892 amending the Waste Framework Directive
        'description': 'Extended producer responsibility for textile, textile-related and footwear products, plus binding food waste reduction targets, introduced into Directive 2008/98/EC',
        'applicability': 'Producers, importers, distributors and distance sellers of apparel, home textiles and footwear (Annex IVc CN codes); producer responsibility organisations; online platforms and fulfilment service providers; social economy collectors; food processors, retailers and food service operators',
        'policy_area': 'Environment',
        'priority_level': 'high',
        'keywords': ['textile epr', 'extended producer responsibility', 'waste framework directive', 'textile waste', '2025/1892', 'food waste', 'fibre-to-fibre recycling', 'separate collection of textiles'],
        'date_from': 2025
    },
}


class ClusterCreator:
    """Creates law clusters from package definitions"""

    def __init__(self, dry_run=False):
        self.db = SessionLocal()
        self.dry_run = dry_run
        self.stats = {
            'clusters_created': 0,
            'laws_added': 0,
            'packages_processed': 0
        }

    def find_primary_law(self, celex: str) -> Optional[EULaw]:
        """Find primary law by CELEX"""
        if not celex:
            return None

        return self.db.query(EULaw).filter(
            EULaw.celex == celex
        ).first()

    def find_related_laws_by_citation(self, primary_law: EULaw, max_depth=2) -> List[Tuple[EULaw, str]]:
        """
        Find laws related through citations.

        Returns list of (law, relationship_type) tuples
        """
        related = []

        if not primary_law or not primary_law.celex:
            return related

        # Find laws that cite this law
        # Use PostgreSQL array overlap operator
        from sqlalchemy.dialects.postgresql import array
        implementing_laws = self.db.query(EULaw).filter(
            EULaw.is_primary_legislation == True,
            EULaw.legal_basis.isnot(None),
            EULaw.legal_basis.op('&&')(array([primary_law.celex]))
        ).all()

        for law in implementing_laws:
            # Determine relationship type from doc_type
            doc_type_lower = (law.doc_type or '').lower()
            if 'implementing' in doc_type_lower:
                relationship = 'implementing'
            elif 'delegated' in doc_type_lower:
                relationship = 'delegated'
            elif 'amending' in doc_type_lower:
                relationship = 'amending'
            else:
                relationship = 'related'

            related.append((law, relationship))

        # Find laws cited by this law
        if primary_law.citations:
            for citation in primary_law.citations[:10]:  # Limit to first 10
                cited_law = self.db.query(EULaw).filter(
                    EULaw.celex == citation,
                    EULaw.is_primary_legislation == True
                ).first()

                if cited_law:
                    related.append((cited_law, 'cited'))

        return related

    def find_related_laws_by_keywords(self, keywords: List[str], date_from: int, limit=50) -> List[EULaw]:
        """Find laws by keyword search in title and subject matter"""
        # Build OR conditions for keywords
        conditions = []
        for keyword in keywords:
            conditions.append(EULaw.title.ilike(f'%{keyword}%'))

        laws = self.db.query(EULaw).filter(
            EULaw.is_primary_legislation == True,
            EULaw.date >= datetime(date_from, 1, 1).date(),
            or_(*conditions)
        ).limit(limit).all()

        return laws

    def create_cluster(self, package_key: str, package_def: Dict) -> Optional[int]:
        """Create a law cluster from package definition"""

        print(f"\n{'='*80}")
        print(f"📦 Creating cluster: {package_def['name']}")
        print(f"{'='*80}")

        # Check if cluster already exists
        existing = self.db.query(LawCluster).filter(
            LawCluster.name == package_def['name']
        ).first()

        if existing:
            print(f"⚠️  Cluster already exists (ID: {existing.id})")
            if not self.dry_run:
                # Delete existing and recreate
                self.db.query(ClusterLaw).filter(
                    ClusterLaw.cluster_id == existing.id
                ).delete()
                self.db.query(LawCluster).filter(
                    LawCluster.id == existing.id
                ).delete()
                self.db.commit()
                print(f"   Deleted existing cluster to recreate")

        # Find primary law
        primary_law = None
        primary_law_id = None

        if package_def['primary_celex']:
            primary_law = self.find_primary_law(package_def['primary_celex'])
            if primary_law:
                primary_law_id = primary_law.id
                print(f"✅ Found primary law: {primary_law.celex}")
                print(f"   {primary_law.title[:80]}...")
            else:
                print(f"⚠️  Primary law {package_def['primary_celex']} not found in database")

        # Create cluster
        if not self.dry_run:
            cluster = LawCluster(
                name=package_def['name'],
                primary_law_id=primary_law_id,
                description=package_def['description'],
                applicability=package_def['applicability'],
                policy_area=package_def['policy_area'],
                priority_level=package_def['priority_level']
            )
            self.db.add(cluster)
            self.db.flush()  # Get cluster.id
            cluster_id = cluster.id
            print(f"✅ Created cluster (ID: {cluster_id})")
        else:
            cluster_id = -1  # Dummy ID for dry run
            print(f"🔍 DRY RUN: Would create cluster")

        # Find and add related laws
        laws_to_add = []

        # 1. Add primary law
        if primary_law:
            laws_to_add.append((primary_law, 'primary'))

        # 2. Find laws by citation network
        if primary_law:
            print(f"\n🔗 Finding related laws by citation network...")
            related_by_citation = self.find_related_laws_by_citation(primary_law)
            print(f"   Found {len(related_by_citation)} laws via citations")
            laws_to_add.extend(related_by_citation)

        # 3. Find laws by keywords
        print(f"\n🔍 Finding related laws by keywords: {', '.join(package_def['keywords'][:3])}...")
        related_by_keywords = self.find_related_laws_by_keywords(
            package_def['keywords'],
            package_def['date_from'],
            limit=50
        )
        print(f"   Found {len(related_by_keywords)} laws via keywords")

        # Add keyword matches as 'related'
        for law in related_by_keywords:
            # Don't add if already in list
            if not any(l.id == law.id for l, _ in laws_to_add):
                laws_to_add.append((law, 'related'))

        # Remove duplicates (keep first occurrence)
        seen_ids = set()
        unique_laws = []
        for law, rel_type in laws_to_add:
            if law.id not in seen_ids:
                seen_ids.add(law.id)
                unique_laws.append((law, rel_type))

        print(f"\n📊 Total unique laws to add: {len(unique_laws)}")

        # Add to cluster
        if not self.dry_run:
            for law, relationship_type in unique_laws[:100]:  # Limit to 100 laws per cluster
                cluster_law = ClusterLaw(
                    cluster_id=cluster_id,
                    law_id=law.id,
                    relationship_type=relationship_type
                )
                self.db.add(cluster_law)

            self.db.commit()
            print(f"✅ Added {len(unique_laws[:100])} laws to cluster")
        else:
            print(f"🔍 DRY RUN: Would add {len(unique_laws[:100])} laws")

        # Show sample laws
        print(f"\n📝 Sample laws in cluster:")
        for i, (law, rel_type) in enumerate(unique_laws[:10], 1):
            print(f"   {i:2d}. [{rel_type:12s}] {law.celex or law.uuid[:8]:20s}")
            print(f"       {law.title[:75]}...")

        self.stats['clusters_created'] += 1
        self.stats['laws_added'] += len(unique_laws[:100])

        return cluster_id

    def create_all_clusters(self, package_filter: Optional[str] = None):
        """Create all defined clusters"""

        packages_to_process = LAW_PACKAGES

        if package_filter:
            if package_filter in LAW_PACKAGES:
                packages_to_process = {package_filter: LAW_PACKAGES[package_filter]}
            else:
                print(f"❌ Unknown package: {package_filter}")
                print(f"Available packages: {', '.join(LAW_PACKAGES.keys())}")
                return

        print(f"🚀 Creating {len(packages_to_process)} law clusters...")

        for package_key, package_def in packages_to_process.items():
            try:
                self.create_cluster(package_key, package_def)
                self.stats['packages_processed'] += 1
            except Exception as e:
                print(f"\n❌ Failed to create cluster {package_key}: {str(e)}")
                import traceback
                traceback.print_exc()

    def show_statistics(self):
        """Display final statistics"""
        print(f"\n{'='*80}")
        print(f"CLUSTER CREATION COMPLETE")
        print(f"{'='*80}")
        print(f"\n📊 STATISTICS:")
        print(f"   Packages processed: {self.stats['packages_processed']}")
        print(f"   Clusters created: {self.stats['clusters_created']}")
        print(f"   Total laws added: {self.stats['laws_added']}")

    def close(self):
        """Close database connection"""
        self.db.close()


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Create curated law packages (clusters)"
    )

    parser.add_argument(
        '--package',
        type=str,
        help=f'Create only specific package. Options: {", ".join(LAW_PACKAGES.keys())}'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be created without committing'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("CREATE CURATED LAW PACKAGES")
    print("=" * 80)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.dry_run:
        print("\n⚠️  DRY RUN MODE - No changes will be committed")

    creator = ClusterCreator(dry_run=args.dry_run)

    try:
        creator.create_all_clusters(package_filter=args.package)
        creator.show_statistics()

        if not args.dry_run:
            print(f"\n✅ Clusters created successfully!")
            print(f"\n💡 View clusters:")
            print(f"   SELECT * FROM law_clusters;")
            print(f"   SELECT cluster_id, COUNT(*) FROM cluster_laws GROUP BY cluster_id;")
        else:
            print(f"\n💡 This was a dry run. Run without --dry-run to commit changes.")

    except Exception as e:
        print(f"\n❌ Failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        creator.close()


if __name__ == "__main__":
    main()
