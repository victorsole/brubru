# Legislative Train: the EPRS tracker of Commission priority files

## QUICK FACTS

- **What it is:** The Legislative Train Schedule is the European Parliament's official tracker for Commission priority legislative and non-legislative files, organised using railway metaphors (trains = Commission priorities, carriages = individual files within a priority)
- **Who maintains it:** European Parliamentary Research Service (EPRS) in cooperation with EP communications; hosted at `europarl.europa.eu/legislative-train/`
- **URL pattern (homepage):** `https://www.europarl.europa.eu/legislative-train/`
- **URL pattern (individual carriage):** `europarl.europa.eu/legislative-train/theme-{priority-slug}/file-{file-slug}` (e.g. `theme-a-new-era-for-european-defence-and-security/file-european-defence-industry-programme`)
- **Current mandate:** Von der Leyen II, 2024-2029; historical data from Von der Leyen I (2019-2024) and earlier mandates is archived on the same site
- **7 priority trains (2024-2029):**
  1. A New Plan for Europe's Sustainable Prosperity and Competitiveness
  2. A New Era for European Defence and Security
  3. Supporting People, Strengthening Our Societies and Our Social Model
  4. Sustaining Our Quality of Life: Food Security, Water and Nature
  5. Protecting Our Democracy, Upholding Our Values
  6. A Global Europe: Leveraging Our Power and Partnerships
  7. Delivering Together and Preparing Our Union for the Future
- **Status enum (7 values):** Legislative initiative / Announced / Tabled / Blocked (no progress for 9 or more months) / Close to adoption / Adopted/Completed / Withdrawn
- **Active scope (2024-2029):** approximately 86 tabled files plus 155 files in other statuses; approximately 80 thematic packages across all mandates
- **EP committees:** 19 standing committees; each carriage is assigned a lead committee (and a joint committee where codecision applies across remits)
- **Update cadence:** monthly (EPRS reviews continuously)
- **Train vs OEIL:** The Train covers only Commission priority files and shows political momentum; the Legislative Observatory (OEIL) covers ALL EP procedures with full procedural detail (committee reports, amendments, voting records, interinstitutional stages)
- **Train vs law-tracker.europa.eu:** The Train stops at adoption; `law-tracker.europa.eu` covers the post-adoption lifecycle (transposition deadlines, Member State implementation, infringement proceedings)
- **Joint Declaration on Priorities (JD):** Annual three-way agreement between EP, Council, and Commission on shared legislative priorities; files tagged JD-year appear in the Spotlight section of the Train
- **Brubru surface:** MEUB tab 1.9 "Legislative Train: state of play"
- **Related guides:** `ep_documents_and_open_data`, `eu_legislative_procedures_explained`, `eu_law_application_monitoring`


## What the Legislative Train is

The Legislative Train Schedule is a public tracking tool produced by the European Parliamentary Research Service (EPRS). It answers a single practical question: where is this Commission priority file right now, and is it moving?

The metaphor is deliberate. A Commission priority (e.g. the Savings and Investments Union package) is a train. The individual proposals within that priority (e.g. the Listing Act, the Retail Investment Strategy) are carriages attached to that train. A carriage can be in motion (Tabled, Close to adoption), stalled (Blocked), or at its destination (Adopted/Completed), or it can have been unhitched entirely (Withdrawn).

The tool covers both legislative files (regulations, directives, decisions going through ordinary or special legislative procedure) and non-legislative files (communications, white papers, action plans, international agreements). Only files that form part of a Commission priority programme are included: the Train is a political map, not an exhaustive procedural register.

The site covers the current parliamentary mandate (2024-2029) and archives mandates back to 2014-2019, enabling comparison of delivery rates across Commission programmes.


## The 7 Priority Trains (Von der Leyen II, 2024-2029)

Each train corresponds to one of the seven political guidelines of Commission President Ursula von der Leyen for the 2024-2029 mandate. The guidelines were published in July 2024 and translated into the Commission Work Programme from autumn 2024 onwards.

| Train number | Short label | Core policy areas |
|---|---|---|
| 1 | Prosperity and Competitiveness | Internal market, industrial strategy, SMEs, single market for services, competition, trade |
| 2 | Defence and Security | European Defence Fund, EDIP, defence industry, cyber, border management |
| 3 | People, Societies, Social Model | Jobs, wages, housing, health, education, equality |
| 4 | Quality of Life | Agriculture (Vision for Agriculture and Food), water, nature, food security |
| 5 | Democracy and Values | Rule of law, media freedom, electoral integrity, anti-corruption |
| 6 | Global Europe | Trade agreements, enlargement, development, humanitarian aid, CFSP |
| 7 | Delivering Together | MFF 2028-2034, own resources, simplification, better regulation |

Train 7 includes the forthcoming Multiannual Financial Framework (MFF) for 2028-2034, which is currently one of the most intensively tracked clusters on the site.

Each train page lists all carriages in that priority grouping, filterable by status and EP committee.


## Status State Machine

A carriage moves through seven statuses in rough sequence, though it can skip steps or reverse.

| Status | Meaning | Typical trigger |
|---|---|---|
| Legislative initiative | Commission has signalled intent but not yet published a formal roadmap | Political guidelines, Work Programme mention |
| Announced | Commission has published an inception impact assessment or roadmap | Formal advance notice on Have Your Say portal |
| Tabled | Commission has formally adopted and published the proposal | College of Commissioners adoption; publication in OJ C or OJ L series |
| Close to adoption | Trilogue concluded or first-reading agreement reached; formal adoption pending | Political deal between EP and Council; awaiting legal-linguistic finalisation |
| Blocked | No institutional progress for 9 or more months | Council presidency deadlock, EP committee disagreement, inter-institutional standstill |
| Adopted/Completed | File has completed the legislative process | Entry into force of the final act; for non-legislative files, publication of the communication or action plan |
| Withdrawn | Commission has formally withdrawn the proposal | Commission Work Programme revision; political decision not to proceed |

The "Blocked" threshold of 9 months is fixed: EPRS applies it automatically based on the last recorded institutional movement. A file labelled Blocked is not necessarily dead, it is a factual observation, not a political verdict. Files frequently move from Blocked back to Tabled or Close to adoption after a change in Council presidency or a political deal.

"Legislative initiative" is technically a pre-proposal status. It covers files mentioned in the Commission Work Programme or Political Guidelines where no roadmap has yet been published. These carriages appear on the Train to give a complete picture of the Commission's agenda.


## What a "Carriage" is

A carriage is the Train's term for a single legislative or non-legislative file. Each carriage page on the Train displays:

- **Title:** The official short title of the proposal or initiative (e.g. "Artificial Intelligence Act")
- **Type:** Legislative or non-legislative; sub-type (regulation, directive, international agreement, communication, etc.)
- **Status:** Current status in the seven-value enum (see above)
- **Lead committee:** The EP committee responsible for the file (e.g. IMCO, LIBE, ECON); joint committee arrangements noted where applicable
- **Interinstitutional reference:** The EP procedure reference (COD, CNS, APP format; see `eu_legislative_procedures_explained`)
- **Commission document reference:** The COM(YYYY)NNN number where the proposal has been tabled
- **OEIL link:** Direct link to the corresponding OEIL procedure file for full procedural detail
- **EUR-Lex link:** Direct link to the legislative text or proposal on EUR-Lex
- **Key milestones:** Timeline of major procedural events (Commission adoption, committee vote, plenary vote, Council general approach, trilogue conclusion)
- **Related carriages:** Other files in the same package or theme that are procedurally linked

A single Commission package (e.g. the Clean Energy Package, the AI Package) typically contains multiple carriages, each with its own status and lead committee. It is common for carriages in the same package to be at very different stages: one regulation may be Adopted while the accompanying directive is still Tabled.


## The Train, OEIL, and law-tracker: a comparison

| Feature | Legislative Train | OEIL (Legislative Observatory) | law-tracker.europa.eu |
|---|---|---|---|
| Scope | Commission priority files only | All EP procedures (thousands) | Post-adoption lifecycle only |
| Maintained by | EPRS / EP communications | EP Directorate-General for the Presidency | European Commission (DG GROW / Publications Office) |
| Granularity | Political status summary | Full procedural record (every document, vote, position) | Transposition deadlines, national measures, infringement |
| Best for | "Is X moving?" / political momentum | "What happened at committee stage?" / document retrieval | "Has Member State Y transposed directive Z?" |
| Start point | Commission Work Programme / Political Guidelines | Formal referral to EP | Entry into force of the adopted act |
| End point | Adoption or Withdrawal | Formal closure of EP procedure | Transposition complete or infringement closed |
| URL pattern | `europarl.europa.eu/legislative-train/theme-{x}/file-{y}` | `oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=YYYY/NNNN(XXX)` | `law-tracker.europa.eu` |
| Free text search | Yes (by title, keyword, committee, status) | Yes (by reference, rapporteur, keyword) | Yes (by act title or CELEX) |
| Machine-readable API | No official public API | Limited (EP Open Data Portal) | No official public API |

For users asking "what is the status of the AI Act", the Train gives a one-line political answer. For users asking "what amendments did LIBE table in first reading", OEIL is the correct tool. For users asking "has France transposed the NIS2 Directive", law-tracker is the starting point.

See `ep_documents_and_open_data` for the EP Open Data Portal which underpins OEIL data exports, and `eu_law_application_monitoring` for post-adoption monitoring tools including law-tracker.


## Packages and Spotlight

### Packages

The Train organises carriages into approximately 80 thematic packages across all mandates. A package is a sub-grouping within a priority train: for example, Train 1 (Prosperity and Competitiveness) contains the "Savings and Investments Union" package, the "European Product Act" package, the "Digital Single Market Package", and others.

Packages are useful when a user is following a Commission legislative strategy rather than a single file. Searching by package shows all related carriages simultaneously, including those that have already been adopted.

### Spotlight

The Spotlight section highlights curated groupings of files that cut across the seven priority trains:

- **Joint Declarations on Priorities (JD26, JD23-24, etc.):** Files agreed in the annual three-way legislative priorities declaration (see below)
- **Simplification 2024-2029:** Cross-cutting simplification files targeting the Commission's Competitiveness Compass agenda
- **MFF 2028-2034:** All files relating to the next Multiannual Financial Framework
- **COVID-19 response:** Historical grouping of emergency measures from 2020-2021

The Spotlight is the fastest way to see what the three institutions have collectively committed to legislate in any given year.


## Joint Declaration on Priorities

Each autumn, the Presidents of the European Parliament, the Council, and the European Commission sign a Joint Declaration on the EU's legislative priorities for the coming year. This is a political commitment to prioritise certain files in the interinstitutional timetable.

Files covered by the current Joint Declaration (JD26 for 2026 priorities) appear in the Spotlight section of the Train with a dedicated tag. These files are typically those where all three institutions have agreed to accelerate work. The JD does not create any legal obligation, but it functions as a coordination signal: rapporteurs, shadow rapporteurs, and Council working party chairs know that these files have political backing to advance.

As of June 2026, JD26 contains approximately 5 tabled, 19 blocked, 2 close to adoption, and 2 withdrawn files, illustrating that political commitment does not automatically unblock institutional deadlock.

Previous declarations (JD23-24, JD22, JD21, JD18) are also browsable on the Train, enabling analysis of which files were prioritised in earlier mandates and whether they were eventually adopted.


## How to Search the Train

The Train's search interface at `https://www.europarl.europa.eu/legislative-train/search` supports the following filters, which can be combined:

- **Status:** One or more of the seven status values
- **EC priority train:** One of the seven 2024-2029 priorities (or previous mandate priorities)
- **EP committee:** One of the 19 standing committees (e.g. AFET, BUDG, CONT, CULT, DEVE, ECON, EMPL, ENVI, FEMM, IMCO, INTA, ITRE, JURI, LIBE, PECH, PETI, REGI, TRAN, AFCO)
- **Type:** Legislative / Non-legislative / International agreement / Undefined
- **Package:** Any of the approximately 80 named thematic packages
- **Spotlight grouping:** Joint Declarations, Simplification, MFF, or other curated sets

Practical examples:

- To find all files Blocked in the Defence and Security train: set Priority = Train 2, Status = Blocked
- To find all files assigned to the ECON committee that are close to adoption: set Committee = ECON, Status = Close to adoption
- To find all files in the Savings and Investments Union package regardless of status: set Package = "Savings and Investments Union"

The search does not support full-text search within carriage descriptions. For document-level search (committee reports, legislative texts), use `ep_documents_and_open_data` or EUR-Lex directly.


## How Brubru Uses the Train

Brubru surfaces the Legislative Train at **MEUB tab 1.9: "Legislative Train: state of play"**. This tab allows users to:

- Browse carriages linked to their tracked policy interests (set at MEUB 1.2 Policy Interests)
- See the current status of files relevant to their portfolio
- Navigate directly to the EP carriage page or to the OEIL procedure file

Brubru's internal carriages database (the `legislative_carriages` table, updated daily) ingests the Train's data and cross-references it with OEIL procedure references and CELEX numbers where available. This enables MEUB 1.9 to show not just Train status but also the most recent committee report or plenary vote date sourced from OEIL.

When a user asks "is X in the train" or "what status is X in the train", Brubru will query the carriages table and return the current Train status, the priority train it belongs to, the lead committee, and a direct link to the carriage page. When a file is not on the Train (because it is not a Commission priority file), Brubru will clarify that the file exists in OEIL but has not been included in the Commission's priority programme.

The `eu_legislative_procedures_explained` guide covers the procedural stages (first reading, second reading, conciliation) that underpin what the Train statuses describe at a political level.
