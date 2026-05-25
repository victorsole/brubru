# EU Legislative Procedures — Ordinary, Special and Non-Legislative

## QUICK FACTS
- **Three families**: the **ordinary legislative procedure** (codecision, the default), the **special legislative procedures** (consent and consultation), and **non-legislative procedures** (delegated and implementing acts, "NLE" enactments).
- **Ordinary (codecision)** — Article **294 TFEU**: Parliament and Council adopt jointly as **equal co-legislators** on a Commission proposal. The most common EU lawmaking route.
- **Special** — Article **289(2) TFEU**: the Council is the **sole legislator** and Parliament either **consents** (accept/reject, no amendment) or is **consulted** (non-binding opinion).
- **Non-legislative** — **delegated acts** (Art **290 TFEU**, supplement/amend non-essential parts) and **implementing acts** (Art **291 TFEU**, uniform implementation via comitology committees).
- **Why Brubru cares**: procedure type drives Predictions, Position Analysis, the Legislative Tracker, and how the chatbot explains where a file sits. OEIL procedure refs (e.g. `2021/0106(COD)`) encode the type. Source: EUR-Lex LEGISSUM summaries.

## Ordinary legislative procedure (codecision) — Art 294 TFEU
- EP and Council are **co-legislators on an equal footing** (since Maastricht; renamed and extended by Lisbon).
- Structure: **one or two readings**, plus a **conciliation procedure** and third reading if needed.
- **Voting**: Council by **qualified majority**; EP by **simple majority** of votes cast at first and third readings, and by **majority of its component Members** at second reading.
- Procedure code in OEIL: **`(COD)`**, e.g. `2021/0106(COD)` (the AI Act).
- Most files reach agreement at first reading via **trilogues** (informal EP–Council–Commission negotiations).

## Special legislative procedures — Art 289(2) TFEU
The Council legislates alone in specific Treaty-defined cases; Parliament's role is either:
- **Consent procedure**: Parliament can **accept or reject** by absolute majority but **cannot amend**; the Council cannot override the EP's position. Used for, e.g., anti-discrimination legislation (Art 19), certain international agreements (Art 218(6)(a)), accession of new Member States, Article 7 TEU breaches, Article 50 TEU withdrawal. OEIL code **`(APP)`**.
- **Consultation procedure**: the Council adopts only after Parliament gives an **opinion**, which it may approve, reject or propose amendments to, but which is **not legally binding** on the Council. Used for, e.g., competition policy (Art 103 TFEU) and harmonisation of indirect taxation (Art 113 TFEU). OEIL code **`(CNS)`**.

## Non-legislative procedures (NLE)
Acts adopted outside the ordinary/special legislative routes:
- **Delegated acts (Art 290 TFEU)**: the legislator empowers the Commission to adopt acts that **supplement or amend non-essential parts** of a basic act. Parliament and Council can **revoke** the delegation or **object** to a specific delegated act. OEIL often tags these **`(DEA)`**.
- **Implementing acts (Art 291 TFEU)**: where uniform implementing conditions are needed, the Commission (or, exceptionally, the Council) adopts them, generally after a **comitology committee** of Member-State representatives. OEIL code **`(RPS)`/`(COD)`**-adjacent depending on control.
- Implementing and delegated acts **may not exceed the framework** of the basic act.
- Other NLE examples: ratification of international agreements (Art 218), Article 7 TEU fundamental-rights cases, Article 49 TEU accession, Article 50 TEU withdrawal arrangements. OEIL code **`(NLE)`**.

## How procedure codes map (OEIL → meaning)
| OEIL code | Procedure |
|---|---|
| `(COD)` | Ordinary legislative procedure (codecision) |
| `(CNS)` | Consultation (special) |
| `(APP)` | Consent (special) |
| `(NLE)` | Non-legislative enactment |
| `(BUD)` / `(DEC)` | Budgetary / discharge |
| `(INI)` | Own-initiative report (non-binding EP report) |
| `(RSP)` | Resolution |

## How Brubru uses this
- **Predictions / Position Analysis** weight EP group positions differently by procedure (codecision = EP is decisive; consultation = EP opinion is advisory).
- **Legislative Tracker** stores the OEIL procedure ref; the code's suffix tells the chatbot which institutions decide.
- **Chat** should explain, when asked "what stage is X at?", both the procedure type and what the next step is (committee report → plenary vote → trilogue → Council adoption → OJ).

## Cross-references
- `finding_and_citing_eu_law.md` — the data hub
- `celex_number_format.md` — CELEX vs OEIL procedure numbering (independent counters)
- `official_journal_explained.md` — how an adopted act reaches the OJ
- `european_parliament_structure.md` — committees, rapporteurs and how the EP organises its side of the procedure
- `eu_interinstitutional_relations.md` — EP / Council / Commission roles (if present)
