# EU JHA Interoperability Framework: Regulations 2019/817 and 2019/818

## QUICK FACTS
- Full name: Regulation (EU) 2019/817 (borders and visa side) and Regulation (EU) 2019/818 (police and judicial cooperation, asylum and migration side) establishing interoperability between EU information systems
- CELEX: 32019R0817 (2019/817) and 32019R0818 (2019/818)
- Adopted: 20 May 2019, by the European Parliament and the Council
- Entry into force: 11 June 2019
- Type: Regulations (directly applicable), a matched pair covering different legal bases (Schengen/borders acquis vs police, judicial cooperation, asylum and migration acquis)
- Purpose: make the EU's large-scale information systems in the Justice and Home Affairs (JHA) space work together, so a single query can check multiple databases and reveal whether one person is using several identities
- Five components established: European Search Portal (ESP), shared Biometric Matching Service (sBMS), Common Identity Repository (CIR), Multiple-Identity Detector (MID), Central Repository for Reporting and Statistics (CRRS)
- Systems integrated: SIS (Schengen Information System), VIS (Visa Information System), Eurodac, EES (Entry/Exit System), ETIAS (European Travel Information and Authorisation System), ECRIS-TCN (European Criminal Records Information System for third-country nationals); Europol data is also queryable via the ESP
- Lead agency: eu-LISA (EU Agency for the Operational Management of Large-Scale IT Systems in the Area of Freedom, Security and Justice)
- Deployment status (2026): sBMS operational from 2025; ESP and CIR went live around 12 June 2026, aligned with the New Pact on Migration and Asylum application date; full operational capacity targeted for 2027
- MID link colours: white (no identity conflict), green (confirmed same identity, no conflict), yellow (potential identity conflict requiring manual verification), red (confirmed multiple-identity fraud or identity conflict)
- Fundamental-rights oversight: European Union Agency for Fundamental Rights (FRA) issued its Opinion on interoperability in April 2018; European Data Protection Supervisor (EDPS) provides ongoing supervision and has flagged interoperability as a "point of no return" for data-protection principles
- Responsible DG: DG HOME (Migration and Home Affairs)
- Responsible Commissioner: Magnus Brunner (Migration and Internal Affairs)
- Legal basis: Article 16(2), Article 74, Article 78(2)(e), Article 79(2)(c), Article 82(1)(d), Article 85(1), Article 87(2)(a) and Article 88(2) TFEU (split across the two Regulations depending on policy field)

## Overview

The interoperability framework is the plumbing layer connecting the EU's separate large-scale JHA databases. Before 2019, SIS, VIS, Eurodac, EES, ETIAS and ECRIS-TCN each operated as a silo: a border guard, police officer or asylum caseworker had to query each system individually, and the same person could appear under different identities in different systems without anyone noticing.

Regulation (EU) 2019/817 and Regulation (EU) 2019/818 are a matched legislative pair adopted the same day (20 May 2019) under different legal bases. 2019/817 covers the borders and visa policy field; 2019/818 covers police and judicial cooperation, asylum and migration. Together they create one technical and legal architecture built around five shared components, operated centrally by eu-LISA on behalf of the Member States and EU agencies (notably Europol and Frontex).

The framework does not create a new database of its own. It sits on top of the existing systems, allowing a single search to be routed across all of them and surfacing where the same biometric or biographic data appears more than once.

## The Five Components

**European Search Portal (ESP)**: A single-query gateway. Authorised users (border guards, police, immigration officers, consular staff) submit one search that is routed simultaneously to SIS, VIS, Eurodac, EES, ETIAS, ECRIS-TCN, Europol data and Interpol databases, according to each user's access rights. It functions as a message router rather than a database in its own right.

**Shared Biometric Matching Service (sBMS)**: The biometric engine. Converts fingerprints and facial images submitted to any connected system into biometric templates and performs cross-system one-to-many matching, so a fingerprint enrolled under one system can be checked against biometric data held in the others.

**Common Identity Repository (CIR)**: A shared biographical and travel-document data store for third-country nationals known to the connected systems (excluding SIS, which keeps its own separate architecture for alerts). Law enforcement access to the CIR is a two-step "hit/no-hit" process: a first query only confirms whether a record exists, and a second, justified query is needed to see the underlying data.

**Multiple-Identity Detector (MID)**: Creates and stores links between identities found across the connected systems, using a colour-coded classification (white, green, yellow, red). Yellow and red links normally require manual human verification by the Member State or agency that created the underlying record, to prevent automated systems alone from determining that someone is committing identity fraud.

**Central Repository for Reporting and Statistics (CRRS)**: An anonymised analytical repository for cross-system statistics and reporting, used to monitor migration trends, data quality and the operation of the interoperability components, without allowing identification of individuals from the aggregated data.

## Systems Integrated

| System | Full name | Domain |
|--------|-----------|--------|
| SIS | Schengen Information System | Alerts on persons and objects, law enforcement and border checks |
| VIS | Visa Information System | Short-stay Schengen visa data |
| Eurodac | European Dactyloscopy | Biometric database for asylum seekers and irregular migrants (recast Regulation (EU) 2024/1358 -- see `eurodac_asylum_migration`) |
| EES | Entry/Exit System | Records entry, exit and refusal of entry for third-country nationals |
| ETIAS | European Travel Information and Authorisation System | Pre-travel screening for visa-exempt third-country nationals |
| ECRIS-TCN | European Criminal Records Information System for third-country nationals | Identifies which Member State holds criminal record data on a non-EU national |

## Deployment Timeline

| Date | Milestone |
|------|-----------|
| 20 May 2019 | Regulations (EU) 2019/817 and 2019/818 adopted |
| 11 June 2019 | Entry into force |
| 2025 | Shared Biometric Matching Service (sBMS) becomes operational |
| 12 June 2026 | European Search Portal (ESP) and Common Identity Repository (CIR) go live, aligned with the New Pact on Migration and Asylum application date |
| 2027 (targeted) | Full operational capacity across all five components, contingent on EES and ETIAS reaching stable operation |

Component rollout depends on the underlying systems being ready. EES and ETIAS both had delayed launches, which pushed back the interoperability timeline in turn (interoperability cannot exceed the readiness of the systems it connects).

## Institutional Landscape

| Body | Role |
|------|------|
| DG HOME | Lead Commission Directorate-General |
| Commissioner Brunner | Migration and Internal Affairs |
| eu-LISA | Operates the ESP, sBMS, CIR, MID and CRRS on behalf of Member States and agencies |
| Europol | Data contributor and user of the ESP for law-enforcement queries |
| Frontex | Border-management data contributor, particularly for EES and ETIAS |
| LIBE Committee (EP) | Parliamentary oversight of JHA legislation |
| JHA Council | Council configuration covering justice and home affairs |
| FRA | Fundamental Rights Agency; issued a dedicated Opinion on interoperability (April 2018) covering non-discrimination, the right to information, and rights of access, correction and deletion |
| EDPS | European Data Protection Supervisor; ongoing supervisory role, works with FRA and Frontex on data-protection safeguards for the framework |

## Fundamental Rights and Data Protection Concerns

Interoperability is one of the most contested pieces of the EU's JHA architecture because it moves the Union from separate-purpose databases (each built for one policy field, with access limited accordingly) towards a connected architecture where a match in one system becomes visible, in a controlled way, to users of another.

Key safeguards written into the Regulations:
- The CIR two-step hit/no-hit access model, meant to limit how much personal data a law-enforcement query reveals before a justified follow-up request
- Mandatory human review of yellow and red MID links before any adverse decision is taken against an individual
- A general fundamental-rights safeguard clause and non-discrimination provisions, reflecting FRA's 2018 Opinion
- The CRRS anonymisation requirement, so statistical use of the data cannot be reverse-engineered to identify individuals

Recurring concerns raised by FRA, the EDPS and academic commentary include: the risk that data-quality errors in one system (for example EES) propagate into asylum or immigration decisions in another; the difficulty of exercising rights of access, correction and deletion across five interlinked components rather than one; and the EDPS characterisation of interoperability as a structural "point of no return" for how EU data-protection principles apply once systems built for different purposes are technically joined.

## Related EU Instruments

- Eurodac recast, Regulation (EU) 2024/1358 -- one of the connected systems, see `eurodac_asylum_migration`
- New Pact on Migration and Asylum -- interoperability components went live alongside the Pact's application date, see `eu_migration_asylum_pact`
- Entry/Exit System, Regulation (EU) 2017/2226 -- see `eu_entry_exit_system_ees_2017_2226`
- ETIAS, Regulation (EU) 2018/1240 -- see `eu_etias_travel_authorisation_2018_1240`
- Schengen Information System -- see `schengen_information_system_sis`
- eu-LISA founding Regulation (EU) 2018/1726 -- see `eulisa_large_scale_it_systems_agency`
- EDPS founding Regulation (EU) 2018/1725 -- see `edps_european_data_protection_supervisor_reg_2018_1725`
- FRA -- see `fra_agency_overview`

## Sources

- Regulation (EU) 2019/817 (CELEX 32019R0817)
- Regulation (EU) 2019/818 (CELEX 32019R0818)
- eu-LISA, Interoperability activities page (eulisa.europa.eu/activities/interoperability)
- eu-LISA, agency overview page (eulisa.europa.eu)
- FRA, Opinion on the impact on fundamental rights of interoperability (April 2018)
- EDPS, "Building strong supervision of the JHA Interoperability Framework"

## Related Brubru Guides

- `eurodac_asylum_migration` -- Recast Eurodac Regulation, one of the connected systems
- `eu_migration_asylum_pact` -- New Pact on Migration and Asylum, whose application date aligned with the ESP/CIR go-live
- `eu_entry_exit_system_ees_2017_2226` -- Entry/Exit System
- `eu_etias_travel_authorisation_2018_1240` -- ETIAS travel authorisation
- `schengen_information_system_sis` -- Schengen Information System
- `eulisa_large_scale_it_systems_agency` -- eu-LISA, the operating agency
- `edps_european_data_protection_supervisor_reg_2018_1725` -- EDPS oversight role
- `fra_agency_overview` -- FRA fundamental-rights oversight role
