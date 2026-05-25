# European Parliament Committees — The 26 Committees and Their Remits

## QUICK FACTS
- **What this is**: the full list of European Parliament committees (term 10, 2024–2029) with their codes and policy remits — so Brubru can answer "which committee handles X?" and route legislative files correctly.
- **Role**: committees do the substantive legislative work. Each file has a **lead committee** (with a rapporteur) and may have **opinion-giving** committees. Committees adopt amendments and reports that go to plenary.
- **Standing committees + subcommittees + special committees**: most are standing committees; **DROI, SEDE, FISC, SANT, EUDS** are subcommittees; **HOUS** is a special committee (term 10). EUDS runs **until 3 February 2027**.
- **Per-committee data**: draft agendas, draft reports, amendments, meeting documents, votes, minutes, work-in-progress, supporting analyses — at `europarl.europa.eu/committees/en/{code}/…` and via the EP Open Data API. See `ep_documents_and_open_data.md`.
- **Composition & operation** (EP "Discover the committees" booklet, 2025): the **720 MEPs** represent ~**440 million** citizens; the legislative work runs through **22 standing committees + 2 subcommittees** (plus, in term 10, additional subcommittees and a special committee — see the table). Each committee elects a **chair + up to 4 vice-chairs**; composition mirrors each political group's weight in Parliament; committees usually meet **once or twice a month**; meetings are **livestreamed** and documents published in **24 languages**.
- **Source**: https://www.europarl.europa.eu/committees/en/home.

## The 26 committees (term 10)
| Code | Committee | Core remit |
|---|---|---|
| **AFET** | Foreign Affairs | EU external policy, CFSP, enlargement, association agreements |
| **DROI** | Human Rights *(subcommittee of AFET)* | Human rights in EU external action |
| **SEDE** | Security and Defence *(subcommittee)* | CSDP, defence industry, security policy |
| **DEVE** | Development | Development cooperation, humanitarian aid, ACP relations |
| **INTA** | International Trade | Common commercial policy, trade agreements, trade defence |
| **BUDG** | Budgets | EU budget, MFF, own resources |
| **CONT** | Budgetary Control | Discharge, anti-fraud (OLAF/EPPO), audit |
| **ECON** | Economic and Monetary Affairs | Economic governance, financial services, banking, EMU |
| **FISC** | Tax Matters *(subcommittee of ECON)* | Taxation, tax avoidance/evasion |
| **EMPL** | Employment and Social Affairs | Labour law, social policy, free movement of workers |
| **ENVI** | Environment, Climate and Food Safety | Environment, climate, public health, food safety |
| **SANT** | Public Health *(subcommittee, term 10)* | Health policy, pharmaceuticals, health security |
| **ITRE** | Industry, Research and Energy | Industrial policy, research, energy, telecoms, digital |
| **IMCO** | Internal Market and Consumer Protection | Single market, consumer protection, customs |
| **TRAN** | Transport and Tourism | Transport policy (all modes), tourism, postal services |
| **REGI** | Regional Development | Cohesion policy, structural funds, outermost regions |
| **AGRI** | Agriculture and Rural Development | CAP, rural development, agri-food |
| **PECH** | Fisheries | Common fisheries policy, fisheries agreements |
| **CULT** | Culture and Education | Education, culture, audiovisual, youth, sport |
| **JURI** | Legal Affairs | EU law, company law, IP, better lawmaking, legal basis checks |
| **LIBE** | Civil Liberties, Justice and Home Affairs | Fundamental rights, data protection, migration, police/judicial cooperation |
| **AFCO** | Constitutional Affairs | Treaties, institutional/electoral matters, interinstitutional relations |
| **FEMM** | Women's Rights and Gender Equality | Gender equality, women's rights |
| **PETI** | Petitions | Citizens' petitions, European Ombudsman relations |
| **EUDS** | European Democracy Shield *(subcommittee, until 3 Feb 2027)* | Foreign interference, disinformation, democratic resilience |
| **HOUS** | Housing *(special committee, term 10)* | The European housing crisis |

## Key roles in a committee
- **Chair + Vice-Chairs** (the committee Bureau).
- **Rapporteur**: drafts the report on a file (one per file, per the lead committee).
- **Shadow rapporteurs**: one per other political group, to negotiate and represent their group.
- **Coordinators**: each group's lead in the committee.
Rapporteur identity is authoritative on **OEIL**, not press — see `feedback_oeil_source_of_truth.md`.

## How Brubru uses this
- **Chat**: "which committee handles AI?" → ITRE/IMCO (lead varies by file); "data protection?" → LIBE; "pharma?" → ENVI/SANT.
- **Legislative Tracker / Predictions**: lead committee + rapporteur drive the timeline and outcome model.
- **My EU Bubble**: committee draft agendas, reports and amendments are scraped/synced (`committee_work_scraper.py`) and surfaced in My Files / Amendments.
- **Calendar**: committee meeting weeks differ from plenary weeks.

## Cross-references
- `european_parliament_structure.md` — how committees fit the whole EP
- `ep_political_groups_overview.md` — groups (rapporteur/shadow allocation)
- `ep_documents_and_open_data.md` — committee documents + Open Data API
- `eu_legislative_procedures_explained.md` — how a committee report reaches plenary
- `docs/api/eu_parliament_data_access.md` — the per-committee URL template + API
