# eu-LISA: EU Agency for the Operational Management of Large-Scale IT Systems in the Area of Freedom, Security and Justice

## QUICK FACTS
- Full name: European Union Agency for the Operational Management of Large-Scale IT Systems in the Area of Freedom, Security and Justice (eu-LISA)
- Legal basis: Regulation (EU) 2018/1726 (CELEX 32018R1726), adopted 14 November 2018, replacing the founding Regulation (EU) 1077/2011
- Operational since: 1 December 2012
- Headquarters: Tallinn, Estonia
- Operational site: Strasbourg, France (day-to-day system operations, 24/7/365 application management)
- Backup site: Sankt Johann im Pongau, Austria (technical continuity site)
- Liaison office: Brussels, Belgium (institutional engagement)
- Staff: approximately 385 across the four sites
- Executive Director: Tillmann Keber (appointed 18 June 2025, took office 1 October 2025)
- Deputy Executive Director: Marili Männik (in post since 16 August 2024; served as Executive Director ad interim until October 2025)
- Governance: Management Board (Member State + Commission representatives, plus Schengen-associated countries) and system-specific Advisory Groups
- Mission: "keep Europe safe through technology" -- operates the EU's centralised large-scale IT systems for borders, migration, asylum and judicial/police cooperation
- Systems operated: SIS (Schengen Information System), VIS (Visa Information System), Eurodac, EES (Entry/Exit System), ETIAS (European Travel Information and Authorisation System), ECRIS-TCN (European Criminal Records Information System for third-country nationals), plus ECRIS-RI, e-CODEX, JITs Collaboration Platform and Prum II
- Interoperability framework: Regulations (EU) 2019/817 and 2019/818, delivering ESP (European Search Portal), CIR (Common Identity Repository), sBMS (shared Biometric Matching Service), MID (Multiple-Identity Detector) and CRRS (Central Repository for Reporting and Statistics)
- Responsible DG: DG HOME (Migration and Home Affairs)
- Responsible Commissioner: Magnus Brunner (Migration and Internal Affairs)
- Parliamentary oversight: LIBE committee (Civil Liberties, Justice and Home Affairs)
- Key partners: Frontex, Europol, Eurojust, EUAA, national border and law-enforcement authorities

## Overview

eu-LISA is the technical engine room of the EU's Area of Freedom, Security and Justice. It does not set policy; it builds, runs and secures the shared IT infrastructure that lets Member States exchange data on borders, visas, asylum and criminal records at EU scale. Every major EU migration and security file -- Schengen, the New Pact on Migration and Asylum, the 2024-2026 borders modernisation wave (EES, ETIAS) -- ultimately depends on eu-LISA's systems working. It is a small, technical agency but an operationally indispensable one: without it, Schengen's compensatory measures and the EU's biometric border checks would not function.

The agency was established by Regulation (EU) 1077/2011 and became operational on 1 December 2012, initially taking over SIS II, VIS and Eurodac from the Commission and Member States. Its mandate was reinforced and expanded by Regulation (EU) 2018/1726, which is the current legal basis and which broadened eu-LISA's role to cover interoperability, EES, ETIAS and ECRIS-TCN as those systems were built.

## Structure and governance

**Management Board**: the main governance body, composed of one representative per Member State plus two Commission representatives, with Schengen-associated countries (Iceland, Liechtenstein, Norway, Switzerland) also participating where relevant to the systems they take part in. The Board adopts the agency's work programme, budget and annual report, and appoints the Executive Director.

**Executive Director**: the agency's legal representative and day-to-day manager, appointed by the Management Board. Tillmann Keber took office on 1 October 2025, succeeding a period in which Deputy Executive Director Marili Männik served as Executive Director ad interim.

**Advisory Groups**: system-specific bodies (one per major IT system) that bring together Member State technical experts to advise the Management Board on operational and technical aspects of each system's development and maintenance.

**Sites**: Tallinn (Estonia) hosts the registered seat and corporate functions; Strasbourg (France) is the main operational site running 24/7/365 application management for the live systems; Sankt Johann im Pongau (Austria) is the technical backup site ensuring business continuity if Strasbourg is unavailable; Brussels (Belgium) hosts a liaison office for engagement with EU institutions.

## Systems operated

| System | Purpose |
|--------|---------|
| SIS (Schengen Information System) | Shared alerts on persons and objects for police, border, customs, visa and judicial authorities; the core compensatory measure for the absence of internal Schengen border checks |
| VIS (Visa Information System) | Stores short-stay Schengen visa data, including biometrics, to combat visa fraud and support consular checks |
| Eurodac | Biometric database (fingerprints and, since the 2024 recast, facial images) of asylum seekers and irregular migrants, used to determine which Member State is responsible for an asylum claim; see `eurodac_asylum_migration` |
| EES (Entry/Exit System) | Electronic register of third-country nationals' entry and exit at the external border, replacing manual passport stamping |
| ETIAS (European Travel Information and Authorisation System) | Pre-travel authorisation and security/migration risk screening for visa-exempt travellers to the Schengen area |
| ECRIS-TCN | Central index allowing Member States to identify which other Member State holds criminal records on a given third-country national or stateless person |
| ECRIS-RI | Reference implementation software connecting national criminal-record registers into the wider ECRIS network |
| e-CODEX | Secure cross-border digital communication channel for judicial authorities and legal professionals |
| JITs Collaboration Platform | Digital collaboration space for cross-border Joint Investigation Teams |
| Prum II | Modernised, centrally routed exchange of biometric and vehicle data between Member State law-enforcement authorities and Europol |

## Interoperability framework

Regulations (EU) 2019/817 (borders and visa) and (EU) 2019/818 (police and judicial cooperation, asylum and migration) require eu-LISA to connect its systems so that authorised users see a unified picture of a person's identity and travel/legal history across systems, without duplicating data unnecessarily. The framework has five components:

- **ESP (European Search Portal)**: a single query point that searches SIS, VIS, Eurodac, EES, ETIAS, ECRIS-TCN and relevant Interpol/Europol databases simultaneously, with results filtered by each user's legal access rights.
- **CIR (Common Identity Repository)**: a shared store of biographical and travel-document data on third-country nationals, enabling a fast "hit/no-hit" check before a user goes through the fuller access procedure for the underlying system.
- **sBMS (shared Biometric Matching Service)**: converts fingerprints and facial images into searchable mathematical templates, enabling one-to-many biometric matching across systems.
- **MID (Multiple-Identity Detector)**: flags links between identity records found via ESP/sBMS, categorised white (confirmed same person), green (confirmed different people), yellow (needs manual verification) or red (confirmed identity fraud).
- **CRRS (Central Repository for Reporting and Statistics)**: an anonymised analytical layer producing migration and border-management statistics and data-quality reports without exposing personal data.

The Eurodac recast (Regulation (EU) 2024/1358), which entered into application on 12 June 2026, was deployed alongside these interoperability components going live, tying the New Pact on Migration and Asylum directly to eu-LISA's technical infrastructure.

## The 2024-2026 deployment wave

eu-LISA has been at the centre of the EU's largest border-IT rollout to date: the Entry/Exit System (EES) and the European Travel Information and Authorisation System (ETIAS), both built on top of the interoperability architecture, alongside the recast Eurodac. Delays in this multi-year programme have repeatedly affected the practical start dates for EES and ETIAS enforcement at external borders, making eu-LISA's delivery timeline a recurring subject of Council and LIBE committee scrutiny.

## Why it matters for EU policy professionals

- eu-LISA sits underneath almost every EU migration, asylum, borders and internal-security file. A legislative change to Eurodac, SIS, EES or ETIAS typically requires a parallel technical implementation track run by eu-LISA, with its own budget, timeline and risk profile.
- Delivery delays at eu-LISA are a standing input to political negotiations: co-legislators repeatedly had to adjust application dates for EES and ETIAS around the agency's technical readiness.
- Data protection and fundamental rights scrutiny of EU border and justice IT systems (European Data Protection Supervisor oversight, LIBE questions) runs directly through eu-LISA's technical choices on biometric matching, retention and interoperability.
- Procurement and industry engagement: eu-LISA runs large IT tenders and industry roundtables (e.g. for EES/ETIAS carrier readiness), a relevant entry point for technology and consultancy stakeholders.

## Key resources

| Resource | URL |
|----------|-----|
| eu-LISA official site | https://www.eulisa.europa.eu/ |
| Who we are | https://www.eulisa.europa.eu/about-us/who-we-are |
| Large-scale IT systems overview | https://www.eulisa.europa.eu/activities/large-scale-it-systems |
| Interoperability | https://www.eulisa.europa.eu/activities/interoperability |
| Founding Regulation (EU) 2018/1726 | CELEX 32018R1726 (EUR-Lex) |
| Founding Regulation (EU) 1077/2011 (superseded) | CELEX 32011R1077 (EUR-Lex) |
| Interoperability Regulations | CELEX 32019R0817 (borders/visa), CELEX 32019R0818 (police/judicial/asylum/migration) |

## Related Brubru guides

- `eurodac_asylum_migration` -- the biometric asylum/migration database eu-LISA operates
- `eu_migration_asylum_pact` -- the wider legislative package Eurodac and EES/ETIAS sit within
- `eu_commission_executive_agencies` -- how EU executive and decentralised agencies fit into the Commission's delivery landscape
