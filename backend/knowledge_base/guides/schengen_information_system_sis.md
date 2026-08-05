# Schengen Information System (SIS): the recast (Regulations 2018/1860, 2018/1861, 2018/1862)

## QUICK FACTS
- Full name: Schengen Information System (SIS), recast legal framework
- Three legal instruments (all adopted 28 November 2018, entered into force 27 December 2018):
  - Regulation (EU) 2018/1860 (CELEX 32018R1860) -- SIS for the return of illegally staying third-country nationals
  - Regulation (EU) 2018/1861 (CELEX 32018R1861) -- SIS in the field of border checks
  - Regulation (EU) 2018/1862 (CELEX 32018R1862) -- SIS in the field of police and judicial cooperation in criminal matters
- Procedure type: Ordinary Legislative Procedure (each Regulation a separate co-decision file)
- Full operation of the recast system: since 7 March 2023 (date set by Commission Implementing Decision (EU) 2023/2017 of 30 January 2023; data migrated from the legacy SIS II over the operational cutover weekend)
- Purpose: the EU's largest and most widely used information-sharing system for security, border management and judicial cooperation, allowing competent national authorities to enter and consult alerts on wanted/missing people and objects in one shared database
- Alert categories (10): persons wanted for arrest/surrender or extradition (European Arrest Warrant); missing persons and children/vulnerable persons needing protective placement; preventive alerts on children at risk of abduction and other vulnerable persons at risk of unauthorised travel; persons sought to assist a judicial procedure (witnesses etc.); persons/objects for discreet, inquiry or specific checks; objects for seizure or use as evidence; refusal of entry or stay (third-country nationals, under Reg. 2018/1861); return decisions (third-country nationals, under Reg. 2018/1860); unknown wanted persons (fingermarks/palmmarks from crime scenes, new category under the recast)
- Biometrics: fingerprints, palm prints, fingermarks and palmmarks searchable via the automated fingerprint identification system (AFIS); DNA profiles for missing persons only; facial images have a legal basis under the recast Regulations for future facial-recognition search, but that search function was not yet technically activated as of the last verified Commission description -- do not assert live facial-recognition search as operational without checking the current eu-LISA/Commission status
- Central system operator: eu-LISA (EU Agency for the Operational Management of Large-Scale IT Systems in the Area of Freedom, Security and Justice); see `eulisa_large_scale_it_systems_agency`
- National layer: each participating country runs its own N.SIS national system plus a SIRENE Bureau (single point of contact for supplementary information exchange and alert coordination)
- Geographic scope: all Schengen area countries (EU Member States applying the Schengen acquis plus Switzerland, Norway, Iceland and Liechtenstein); Ireland and Cyprus participate on a more limited legal basis; Europol has access to all alert categories
- Interoperability: linked with VIS, ETIAS, EES and ECRIS-TCN via the EU interoperability framework (Regulations (EU) 2019/817 and 2019/818) and the shared Common Identity Repository (CIR); see `eu_interoperability_framework_jha_2019_817_818`
- Responsible DG: DG HOME (Migration and Home Affairs)
- Responsible Commissioner: Magnus Brunner (Migration and Internal Affairs)
- EP lead committee: LIBE (Civil Liberties, Justice and Home Affairs)
- Council configuration: Justice and Home Affairs (JHA) Council
- Legal basis: TFEU Articles 77(2), 79(2), 82(1), 85(1), 87(2) and 88(2) depending on the instrument

## Overview

The Schengen Information System is the EU's oldest and most heavily used large-scale IT system for internal security and border management. It has been operational since 1995, was upgraded to a second generation (SIS II) in 2013 to add fingerprint and photograph alerts, and was recast again through three parallel Regulations adopted on 28 November 2018. That recast package entered full operation on 7 March 2023, after national systems migrated their data over a coordinated cutover weekend under a date set by the Commission (Implementing Decision (EU) 2023/2017).

The three-regulation structure exists because of the variable geometry of EU justice and home affairs law: not every Schengen-associated country participates in every policy strand, so the recast splits the legal basis into border checks (2018/1861), return of illegally staying third-country nationals (2018/1860), and police/judicial cooperation (2018/1862). All three regulations state explicitly that this legal split does not affect the principle that SIS is one single operational system.

## What changed in the recast

- New alert category for **return decisions**, allowing Member States to flag third-country nationals subject to a return order so other Schengen states can enforce or recognise it (linked to the EU return policy reform; see `returns_policy_reform`)
- New alert category for **unknown wanted persons**: fingermarks or palmmarks recovered from a terrorism or serious-crime scene can be entered even before the person is identified, and matched automatically as other data is added to SIS
- Expanded **preventive alerts** to protect children at risk of parental abduction and other vulnerable people (adults or minors) at risk of being taken abroad without authorisation, victims of trafficking, gender-based violence or armed conflict
- Wider **biometric toolset**: palm prints and palmmarks added alongside fingerprints; DNA profiles permitted for missing-persons alerts to support identification; legal basis added for facial images and future facial-recognition search
- Mandatory **cross-checking against Interpol databases** (stolen and lost travel documents) for the first time
- Tighter data-quality, deletion-review and fundamental-rights safeguards, including a requirement to assess proportionality before entering an alert on a vulnerable person or a minor
- Full integration into the **EU interoperability architecture**: SIS, VIS, ETIAS, the Entry/Exit System and ECRIS-TCN now share a Common Identity Repository and a European Search Portal, so a single query against one system can surface a hit across the others (see `eu_interoperability_framework_jha_2019_817_818`)

## Alert categories in detail

| Category | Legal basis | What it flags |
|----------|-------------|----------------|
| Arrest/surrender or extradition | Reg. 2018/1862 | Persons subject to a European Arrest Warrant, or an extradition request from Switzerland/Liechtenstein |
| Missing/vulnerable persons | Reg. 2018/1862 | Missing persons, including children, who need to be placed under protection |
| Preventive alerts | Reg. 2018/1862 | Children at risk of parental abduction; vulnerable adults/minors at risk of unauthorised travel, trafficking or gender-based violence |
| Judicial procedure | Reg. 2018/1862 | Witnesses, persons summoned to appear before judicial authorities, persons subject to criminal judgments |
| Discreet, inquiry or specific checks | Reg. 2018/1862 | People or objects to be monitored for the prevention or investigation of serious crime or threats to security |
| Objects for seizure or use as evidence | Reg. 2018/1862 | Vehicles, travel documents, firearms, industrial equipment, banknotes and other property linked to criminal proceedings |
| Refusal of entry or stay | Reg. 2018/1861 | Third-country nationals who should be refused entry to or a residence permit/visa in the Schengen area |
| Return decisions | Reg. 2018/1860 | Third-country nationals subject to a return decision by a Schengen state |
| Unknown wanted persons | Reg. 2018/1862 | Fingermarks/palmmarks from a terrorism or serious-crime scene, entered before the perpetrator is identified |

## Governance and institutional landscape

| Body | Role |
|------|------|
| DG HOME | Lead Commission Directorate-General |
| Commissioner Brunner | Migration and Internal Affairs |
| eu-LISA | Operational management of the Central SIS and the SIS communication infrastructure |
| National SIRENE Bureaux | Supplementary information exchange, alert verification and coordination between countries |
| LIBE Committee (EP) | Parliamentary oversight, co-legislator on any further recast |
| JHA Council | Council configuration for justice and home affairs files |
| Europol | Access to all alert categories; supports cross-border investigations |
| Frontex | Uses SIS alerts in border-management operations |
| National data protection authorities + European Data Protection Supervisor | Joint supervisory coordination group for SIS |

## Key dates

| Date | Event |
|------|-------|
| 1995 | Original SIS becomes operational |
| 2013 | SIS II launched (fingerprint and photograph alerts added) |
| 28 November 2018 | Regulations (EU) 2018/1860, 2018/1861 and 2018/1862 adopted |
| 27 December 2018 | Entry into force of the three Regulations |
| 30 January 2023 | Commission Implementing Decision (EU) 2023/2017 sets the go-live date |
| 7 March 2023 | Recast SIS enters full operation; data migrated from SIS II |

## Related EU information systems

SIS sits alongside a family of EU large-scale IT systems in the area of freedom, security and justice, all operated by eu-LISA and increasingly interoperable:

- **VIS** (Visa Information System) -- Schengen visa applications and decisions
- **EES** (Entry/Exit System) -- biometric entry/exit records for third-country nationals; see `eu_entry_exit_system_ees_2017_2226`
- **ETIAS** (European Travel Information and Authorisation System) -- pre-travel screening for visa-exempt third-country nationals
- **ECRIS-TCN** -- criminal records index for third-country nationals
- **Eurodac** (recast) -- biometric database for asylum applicants and irregular migrants; see `eurodac_asylum_migration`

## Sources

- Regulation (EU) 2018/1860 (CELEX 32018R1860)
- Regulation (EU) 2018/1861 (CELEX 32018R1861)
- Regulation (EU) 2018/1862 (CELEX 32018R1862)
- Commission Implementing Decision (EU) 2023/2017 (go-live date)
- European Commission, DG HOME: "Schengen Information System" and "Alerts and data in SIS", home-affairs.ec.europa.eu
- eu-LISA: SIS system pages and technical reports

## Related Brubru Guides

- `eulisa_large_scale_it_systems_agency` -- the agency that operates SIS
- `eu_interoperability_framework_jha_2019_817_818` -- CIR/ESP interoperability linking SIS to VIS/ETIAS/EES/ECRIS-TCN
- `schengen_borders_code` -- the border-checks rulebook SIS alerts feed into
- `eu_entry_exit_system_ees_2017_2226` -- the biometric entry/exit register alongside SIS
- `europol_agency_overview` -- Europol's SIS access and cross-border investigation role
- `returns_policy_reform` -- the return-decisions alert category and EU returns policy
- `eu_migration_asylum_pact` -- the wider migration/asylum legislative package
- `eurodac_asylum_migration` -- the sibling biometric database for asylum and irregular migration
