# European Parliament Political Groups — Term 10 (2024–2029)

## QUICK FACTS
- **What this is**: the European Parliament's political groups in term 10, with their official `groupCode`s, political character and role — so Brubru can reason about coalitions, rapporteur allocation and likely vote outcomes.
- **MEPs sit by group, not nationality.** A group needs at least **23 MEPs from at least one quarter (7) of Member States**. Groups decide rapporteurships, speaking time, committee coordinators and coordinate voting.
- **8 groups + non-attached** in term 10: **EPP, S&D, Patriots for Europe (PfE), ECR, Renew Europe, Greens/EFA, The Left, Europe of Sovereign Nations (ESN)**, plus **Non-attached (NI)**.
- **The working majority** is typically built around the centre (EPP–S&D–Renew, sometimes with Greens/EFA), file by file. EPP is the largest group and pivotal to most majorities.
- **Why Brubru cares**: group sizes + positions are the core input to **Predictions** and **Position Analysis**; `groupCode`s key the EP MEP-search and Open Data queries.
- **Source**: https://www.europarl.europa.eu/meps/en/search/advanced (group filters) + EP Open Data `/corporate-bodies`.

## The groups and their codes
| Group | `groupCode` | Character |
|---|---|---|
| **EPP** — European People's Party | `7018` | Centre-right, Christian-democrat; largest group |
| **S&D** — Progressive Alliance of Socialists and Democrats | `7038` | Centre-left, social-democrat; second largest |
| **PfE** — Patriots for Europe | `7150` | Right / national-conservative, Eurosceptic (formed 2024) |
| **ECR** — European Conservatives and Reformists | `7037` | Conservative, soft-Eurosceptic |
| **Renew Europe** | `7035` | Liberal / centrist |
| **Greens/EFA** — Greens / European Free Alliance | `7028` | Green + regionalist |
| **The Left** — The Left in the European Parliament (GUE/NGL) | `7036` | Left / socialist |
| **ESN** — Europe of Sovereign Nations | `7151` | Hard-right / sovereigntist (formed 2024) |
| **NI** — Non-attached Members | `6561` | MEPs not in any group |

> Exact seat numbers shift during a term (MEPs change groups, national delegations move). Brubru reads current sizes from the EP Open Data API rather than hard-coding tallies — describe the **ordering and character** unless a current count is verified.

## How groups shape legislation
- **Rapporteurs and shadows** are allocated to groups by a points system (d'Hondt); the lead group on a file drives the report.
- **Coalitions are file-specific**: a centre-right majority (EPP + ECR + PfE/Renew) on some files; a centre/centre-left majority (EPP + S&D + Renew + Greens) on others. Predicting an outcome means estimating which majority forms.
- **Coordinators** negotiate the group line in committee; the group whip guides plenary voting.

## How Brubru uses this
- **Predictions**: combine committee assignment, rapporteur group, shadow positions and group sizes to model the plenary outcome and likely coalition.
- **Position Analysis**: per-group position colouring on a file (`file_position_snapshots`).
- **Chat**: explain group character, who the likely rapporteur group is, and how a vote could split — without inventing precise tallies.
- **Data**: query `/corporate-bodies` (EP Open Data) for current membership; `groupCode` filters the MEP search.

## Cross-references
- `european_parliament_structure.md` — how groups fit the whole EP
- `ep_committees_overview.md` — committees (rapporteur/shadow allocation)
- `eu_legislative_procedures_explained.md` — why the procedure type changes the EP's leverage
- `predictions` skill + `memory/predictions.md` — EP group seats and position colours
- `docs/api/eu_parliament_data_access.md` — `groupCode`s + Open Data `/corporate-bodies`
