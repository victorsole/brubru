# OEIL, the European Parliament's Legislative Observatory

## QUICK FACTS
- **What it is**: OEIL (French: *Observatoire Législatif*, "Legislative Observatory") is the European Parliament's public database tracking the progress of every EU legislative and non-legislative procedure, from the moment a proposal is tabled to final adoption (or rejection/withdrawal).
- **Who runs it**: the European Parliament. **Operational management** sits with the Directorate-General for the Presidency; **technical management** with the Directorate-General for Innovation and Technological Support. Source: https://oeil.europarl.europa.eu/oeil/en/find-out-more
- **Coverage**: every ongoing procedure, plus all procedures submitted to Parliament since the start of the 4th parliamentary term in **July 1994**, when OEIL was launched. The database is updated daily and "in constant evolution since its launch" (EP's own description).
- **Procedure reference format**: `YYYY/NNNN(TYPE)`, e.g. `2021/0106(COD)` (the AI Act) = year the procedure was opened, a sequential procedure number, and a procedure-type code in brackets.
- **Canonical procedure-file URL**: `https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=<procedure reference>`, e.g. `https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=2021/0106(COD)`. This is the pattern Brubru's own `_oeil_url()` builder (`backend/services/comparator/cell_extractors.py`) generates. Raw or URL-encoded brackets (`%28`/`%29`) both work.
- **Only one URL shape is valid**: the canonical `/oeil/en/procedure-file?reference=` pattern above. Any other path under `/oeil/` — in particular the retired pop-up path from the pre-2024 site — returns a 404. Verified 10 August 2026: the canonical URL returns 200 with the full procedure file; the retired path returns a 146-byte 404 page. If a cached link does not match the canonical shape, rebuild it rather than following it.
- **Search entry point**: `https://oeil.europarl.europa.eu/oeil/en/search`.
- **Language coverage**: procedure files and summaries are published in **English and French only** (the underlying source documents linked from a file may exist in more languages).
- **Why Brubru treats OEIL as the source of truth**: OEIL is updated daily directly by Parliament's own administrative services. Press coverage, partner feeds and Brubru's own cached content can lag by days or weeks, especially on rapporteur appointments, shadow-rapporteur lists, and stage-of-procedure status. When OEIL contradicts a cached value anywhere in Brubru, **OEIL wins**. See `feedback_oeil_source_of_truth.md` in project memory.
- **OEIL numbers are NOT CELEX numbers.** A procedure reference like `2021/0106(COD)` and a CELEX identifier like `32024R1689` are produced by two entirely independent numbering systems, run by different institutions (Parliament vs the Publications Office). Never derive one from the other; look each one up separately. See `celex_number_format`.

## What OEIL covers
OEIL exists to make the European Parliament's role in EU decision-making transparent and traceable: its legislative power (co-deciding EU law), its budgetary powers, its right of initiative under Article 225 TFEU, its power to endorse or reject appointments (Commissioners, the Commission President, the ECB President), its role in ratifying international agreements, and its power to object to or revoke delegated acts. Every procedure that touches any of these Parliament functions gets an OEIL procedure file, whether or not Parliament is the lead decision-maker on it.

## The procedure-file structure
Every OEIL procedure file follows the same layout, built from the same underlying record and kept live until the file's final stage:

- **Basic information**: the title of the procedure, its subject classification, the procedure reference, the procedure type, and the stage currently reached. Links to any related procedure files (e.g. a Commission proposal and its accompanying own-initiative report) sit here too.
- **Key players**: the European Parliament committee(s) responsible and giving opinion, the rapporteur and their political group, the shadow rapporteurs appointed by the other political groups, and the Commission Directorate-General and Commissioner formally responsible for the file.
- **Key events**: a chronological timeline of every procedural milestone (Commission adoption, committee referral, committee vote, plenary first reading, trilogue rounds, signature, publication in the Official Journal), each event linked to the underlying document or plenary minutes where one exists.
- **Technical information**: the legal basis (Treaty article), the legislative instrument (regulation, directive, decision), the procedure subtype, any mandatory consultations (e.g. European Economic and Social Committee, Committee of the Regions, European Central Bank), and the internal committee dossier number.
- **Documentation gateway**: the full, chronologically ordered list of every document tied to the file (Commission proposal and impact assessment, EP committee reports and opinions, tabled amendments, Council positions, joint texts), each with its own reference and, where available, a summary and a direct link.
- **Forecast**: for files still in progress, indicative dates for the next committee or plenary stage.
- **Transparency**: on files with an appointed rapporteur, a list of lobbying meetings the rapporteur or shadow rapporteurs have logged with interest representatives, including the organisation's name and meeting date. This surfaces alongside `eu_transparency_register` data.
- **Final act**: once adopted, a direct link to the Official Journal publication and the corresponding CELEX-identified legal act on EUR-Lex.
- **Cross-links**: to IPEX, the interparliamentary exchange platform national parliaments use to monitor EU legislation for subsidiarity checks, and to the file's EUR-Lex record.

Each procedure file can also be downloaded as a PDF snapshot.

## Procedure-type codes
The bracketed code at the end of a procedure reference tells you which decision-making route the file follows:

| Code | Meaning |
|---|---|
| **COD** | Ordinary legislative procedure (co-decision). Parliament and Council are equal co-legislators under Article 294 TFEU. The default and most common route for EU regulations and directives. |
| **CNS** | Special legislative procedure, Parliament consulted (consultation procedure). The Council legislates alone after receiving Parliament's non-binding opinion. |
| **APP** | Special legislative procedure, Parliament's consent required (consent/assent procedure). Parliament can accept or reject as a whole but cannot amend. Used for, among others, most international agreements and accession treaties. |
| **NLE** | Non-legislative enactment. Covers files outside the ordinary/special legislative routes, most commonly the conclusion or ratification of international agreements. |
| **INL** | Legislative-initiative procedure under Article 225 TFEU. Parliament formally requests the Commission to bring forward a legislative proposal (the only own-initiative category that carries this specific Treaty basis). |
| **INI** | Own-initiative report. A non-binding Parliament report or position that is not a formal Article 225 TFEU request. |
| **BUD** | Budgetary procedure. |
| **DEC** | Budgetary discharge procedure (Parliament's annual approval, or refusal, of how the EU budget was implemented). |
| **DEA** | Delegated acts procedure. Tracks the Commission's exercise of delegated powers under a specific parent legislative act, and Parliament/Council's right to object or revoke. |
| **RSP** | Resolution on a topical subject debated and voted in plenary, typically outside a standing legislative file. |

Historical/obsolete codes still visible on older files include ACC (agreement), AVC (assent, the pre-Lisbon name for consent), CNB (consultation of the European Central Bank), CNC (consultation of the Court of Auditors), PRT (Social Protocol procedure) and SYN (cooperation procedure, discontinued after Lisbon).

For the underlying Treaty logic behind these procedures (ordinary vs special vs non-legislative, voting thresholds, trilogues), see `eu_legislative_procedures_explained`.

## Working with OEIL URLs
Always build procedure-file links with the canonical pattern:

```
https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=<reference>
```

Example, the AI Act: https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=2021/0106(COD)

Build every OEIL link from the canonical pattern above and from nothing else. Paths under `/oeil/` that are not `/oeil/en/procedure-file` belong to the retired pre-2024 site and return a 404. If a link fails to resolve, do not guess a similar-looking path: fall back to the OEIL search page (`https://oeil.secure.europarl.europa.eu/oeil/en/search`) or to Brubru's own `_oeil_url()` builder in `backend/services/comparator/cell_extractors.py`, which is the single source of truth for how Brubru itself generates these links.

## Why it matters to a policy professional
- **Rapporteur and shadow-rapporteur identity**: OEIL is the only place these appointments are recorded authoritatively and updated the same day a committee confirms them. Trade press frequently lags by days.
- **Real procedure status**: "awaiting committee decision", "in committee", "in plenary", "awaiting Council's position", "act adopted" and so on are OEIL's own stage labels, and they are the most reliable single indicator of where a file actually stands.
- **Documentation gateway as a research shortcut**: rather than hunting across EUR-Lex, the EP's document register and Council registers separately, a single OEIL file aggregates the Commission proposal, every EP committee report and opinion, tabled amendments, Council documents, and the final act.
- **Transparency data**: the meeting-log section on a rapporteur's page is a fast way to see which organisations have been lobbying a given file.
- **Forecasting**: the "forecast" section gives an indicative date for the next committee or plenary milestone, useful for planning advocacy timing.

## Cross-references
- `eu_legislative_procedures_explained`, the Treaty-level mechanics behind COD, CNS, APP and non-legislative procedures.
- `celex_number_format`, EUR-Lex's independent document-identifier system; never derive a CELEX from an OEIL reference or vice versa.
- `eur_lex_portal`, where the final adopted texts and preparatory documents linked from an OEIL file actually live.
- `ep_rapporteur_shadow_system`, how rapporteurs and shadow rapporteurs are appointed and what their role covers, the detail behind the "key players" section of an OEIL file.
