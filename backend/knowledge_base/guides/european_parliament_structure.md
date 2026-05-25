# The European Parliament — Structure and How Its Work Flows

## QUICK FACTS
- **What it is**: the European Parliament (EP) is the EU's directly-elected co-legislator. Term **10 runs 2024–2029**. It works through the **plenary**, **committees**, **political groups**, **delegations** and a permanent **Secretariat-General**.
- **Four powers**: **legislative** (co-legislator under the ordinary procedure, Art 294 TFEU), **budgetary** (adopts the EU budget + discharge), **supervisory** (elects and scrutinises the Commission), and **external** (consent to international agreements; interparliamentary delegations).
- **Where its data lives**: the **EP Open Data API** (`https://data.europarl.europa.eu/api/v2`, 339 datasets) for MEPs/votes/texts/meetings; **doceo** for documents; **OEIL** for legislative procedures. See `ep_documents_and_open_data.md`.
- **Why Brubru cares**: committees, rapporteurs and group positions drive Predictions, Position Analysis and the Legislative Tracker; the chatbot must know "who does what" to answer accurately.
- **Source**: https://www.europarl.europa.eu/about-parliament/en (Powers and procedures).

## The plenary
The full assembly that takes final decisions. Part-sessions are held mainly in **Strasbourg** (monthly) with additional sittings in **Brussels**. The plenary debates, votes amendments and adopts **texts** (legislative positions, resolutions). Key surfaces: agenda (`OJ-10-{date}-SYN_EN.html`), votes + results, minutes, debates/video, **texts adopted** (`P10_TA(YYYY)NNNN`).

## Committees (26) — where the legislative work happens
Each legislative file is assigned to a **lead committee** (plus opinion-giving committees). A **rapporteur** drafts the report; **shadow rapporteurs** represent the other groups. The committee adopts amendments and a report, which goes to plenary. See `ep_committees_overview.md` for the full list and remits.

Per-committee work surfaces (fixed pattern): draft agendas, draft reports, **amendments**, meeting documents, votes, minutes, work-in-progress, supporting analyses, hearings/workshops/missions.

## Political groups (8) and the non-attached
MEPs sit by **political group**, not nationality. EP10 groups (largest to smallest, by character): **EPP**, **S&D**, **Patriots for Europe (PfE)**, **ECR**, **Renew Europe**, **Greens/EFA**, **The Left**, **Europe of Sovereign Nations (ESN)**, plus **Non-attached (NI)**. Groups decide rapporteurships, speaking time and coordinate voting. See `ep_political_groups_overview.md`.

## Delegations (~48)
Standing **interparliamentary delegations** maintain relations with non-EU parliaments and assemblies (bilateral country delegations like D-US, D-CN, and multilateral assemblies). Each has members, a bureau, ordinary and interparliamentary meetings, and documents.

## Intergroups and bodies
- **Intergroups** (~28): cross-party, cross-committee groupings on themes (e.g. SMEs, animal welfare, LGBTIQ+) — informal, not official EP bodies.
- **Governing bodies**: **Conference of Presidents** (BCPR — group leaders + President, sets the agenda), **Bureau** (BURO — President + 14 Vice-Presidents), **Quaestors** (QUE — members' administrative/financial matters), **Conference of Committee Chairs** (PRCO), **Conference of Delegation Chairs** (PRDE).
- **President** elected for a renewable 2.5-year term; leads plenary and represents the EP.

## The administration
The **Secretariat-General** supports the EP through ~16 Directorates-General (incl. **EPRS** the research service, **COMM** communication, **IPOL/EXPO** policy departments, **TRAD/LINC** translation/interpretation). Headed by the Secretary-General.

## How a file flows (typical ordinary procedure)
1. Commission proposal (COM) → referred to a **lead committee**.
2. **Rapporteur** drafts a report; **amendments** tabled; **shadows** negotiate.
3. **Committee vote** → report adopted.
4. **Plenary** debate + vote → EP position / adopted text (`P10_TA`).
5. **Trilogues** with Council + Commission → provisional agreement.
6. Council adopts → publication in the Official Journal (see `official_journal_explained.md`).

## How Brubru uses this
- **Predictions / Position Analysis**: committee assignment + rapporteur + shadow positions + group sizes feed the outcome model.
- **Legislative Tracker / My Files**: files are tracked by OEIL procedure ref and committee.
- **Chat**: answers "which committee handles X?", "who is the rapporteur?", "what stage is the file at?" by combining this structure with OEIL + EP Open Data.

## Cross-references
- `ep_committees_overview.md` — the 26 committees and their remits
- `ep_political_groups_overview.md` — the 8 groups and codes
- `ep_documents_and_open_data.md` — where EP data and documents live
- `eu_legislative_procedures_explained.md` — ordinary / special / non-legislative procedures
- `docs/api/eu_parliament_data_access.md` — engineering reference (Open Data API, IA, doceo refs)
