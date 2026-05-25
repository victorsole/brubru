# How the European Parliament Plenary Works

## QUICK FACTS
- **What it is**: the **plenary** is the full assembly of all **720 MEPs** (term 10, representing ~440 million EU citizens) — where Parliament takes its final decisions: adopting legislative positions, resolutions, the budget, and electing/scrutinising the Commission.
- **Where**: monthly **part-sessions in Strasbourg** (4 days, Mon–Thu) plus additional **mini-sessions in Brussels**. The seat-of-Parliament split is fixed by the Treaties.
- **Key outputs & references**: agenda `OJ-10-{date}-SYN_EN.html`; adopted texts `P10_TA(YYYY)NNNN`; reports `A10-NNNN/YYYY`; motions `B10-NNNN/YYYY`; joint motions `RC-B…`. Term 10 URLs use `-10-`.
- **Where the data lives**: plenary agendas, votes + results, minutes, verbatim debates (CRE) and adopted texts are on `europarl.europa.eu/plenary/` and in the **EP Open Data API** (`/adopted-texts`, `/meetings`, vote results). See `ep_documents_and_open_data.md`.
- **Why Brubru cares**: plenary votes are the decisive moment for Predictions and Position Analysis; the agenda drives My EU Calendar; adopted texts feed the Legislative Tracker.
- **Source**: EP Plenary guide + `europarl.europa.eu/plenary/en/home.html`.

## The part-session rhythm
- **Strasbourg part-sessions**: roughly monthly, Monday afternoon to Thursday; the main voting sessions.
- **Brussels mini-sessions**: shorter additional sittings for extra business.
- The **EP calendar** (published per year as a PDF) fixes the weeks: plenary weeks, committee weeks, group weeks, constituency (green) weeks.
- The agenda for each session is set by the **Conference of Presidents** (group leaders + the President) on a proposal reflecting committee readiness.

## How a debate-and-vote works
1. **Agenda adoption** at the start of the session (changes possible).
2. **Debate**: the rapporteur presents the committee report; group speakers take allocated time; the Commissioner responds. **"Catch-the-eye"** and **blue-card** questions allow short interventions.
3. **Voting** (fixed voting slots, usually midday): amendments first, then the amended text, then the final legislative resolution.
4. **Voting methods**: show of hands (default), **electronic / roll-call vote** (positions recorded per MEP — the data Brubru uses), or secret ballot (appointments).
5. **Majorities** depend on the procedure: simple majority of votes cast for most ordinary-procedure first/third readings; **absolute majority of component Members** at second reading and for certain decisions (see `eu_legislative_procedures_explained.md`).

## What plenary produces
- **EP legislative position** (`P10_TA`) — the text passed to/with the Council under the ordinary procedure.
- **Resolutions** (own-initiative `INI`, topical `RSP`, urgency resolutions on human rights/breaches of the rule of law).
- **Budget** adoption and **discharge** decisions.
- **Consent** votes (international agreements, accessions) and **appointments** (Commission, Court of Auditors, etc.).
- **Minutes** (record of decisions) and **verbatim report of proceedings (CRE)** — the full multilingual transcript.

## Following plenary (the surfaces)
- **Agenda**: `/plenary/en/agendas.html` and the `OJ-10-{date}-SYN_EN.html` document.
- **Votes & results**: `/plenary/en/votes.html?tab=votes`.
- **Minutes**: `/plenary/en/minutes.html`. **Debates/video**: `/plenary/en/debates-video.html`.
- **Texts adopted**: `/plenary/en/texts-adopted.html` and EP Open Data `/adopted-texts`.

## How Brubru uses this
- **Predictions / Position Analysis**: roll-call vote results (per-MEP, per-group) are the ground truth; plenary outcome confirms or flips the model.
- **My EU Calendar**: plenary weeks + the session agenda are high-velocity events.
- **Legislative Tracker / My Files**: an adopted `P10_TA` text advances a file's status.
- **Chat**: answer "what is the EP voting on this week?" / "what did plenary adopt?" by combining the agenda + adopted texts; cite the `P10_TA` reference.

## Cross-references
- `european_parliament_structure.md` — the EP as a whole
- `ep_committees_overview.md` — where files are prepared before plenary
- `ep_political_groups_overview.md` — who votes how
- `eu_legislative_procedures_explained.md` — readings and majorities
- `ep_documents_and_open_data.md` — plenary data sources + doceo references
- `docs/api/eu_parliament_data_access.md` — engineering reference
