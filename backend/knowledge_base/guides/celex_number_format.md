# CELEX Number Format: the EU Legal-Document Identifier System

## QUICK FACTS
- **What it is**: a CELEX number is the **unique, language-independent identifier** of a document on EUR-Lex. Regulations, directives, decisions, treaties, judgments, COM proposals, consolidated texts and parliamentary questions all have one. Source: the Publications Office tables "Types of documents in EUR-Lex" (https://eur-lex.europa.eu/content/tools/TableOfSectors/types_of_documents_in_eurlex.html) and "CELEX numbers" (https://eur-lex.europa.eu/content/help/eurlex-content/celex-number.html).
- **Anatomy**: **sector (1 character) + year (4) + descriptor (1 to 3 letters, meaning depends on the sector) + number (4 to 6 digits)**. AI Act = `32024R1689` (3 / 2024 / R / 1689). Water Framework Directive = `32000L0060`.
- **12 sectors**: 1 treaties, 2 international agreements, 3 legal acts, 4 complementary legislation, 5 preparatory documents, 6 EU case-law, 7 national transposition measures, 8 national case-law, 9 parliamentary questions, 0 consolidated texts, C OJ C series, E EFTA documents.
- **Suffixes**: corrigendum = same CELEX + `R(xx)` (any sector except 0 and 7), e.g. `32000R1602R(05)`. Consolidated text = sector 0 + the basic act's number + `-YYYYMMDD`, e.g. `02016R0679-20160504`. Transposition = sector 7 + the directive's number + 3-letter country code + `_` + sequence, e.g. `72014L0056FIN_240353`. OJ C notice = `C/YYYY/NNNNN`, e.g. `C/2025/03118`.
- **CELEX is not the procedure number and not the COM number.** `2021/0106(COD)` (OEIL) and `COM(2021) 206` are different identifiers with independent counters; never derive one from another. A COM number converts to a sector-5 CELEX (`52021PC0206` proposal or `52021DC0206` communication).
- **Brubru never invents identifiers**: if a CELEX cannot be checked against Cellar (or EUR-Lex), say so and route the user to the authority.
- **Cellar URL**: `https://publications.europa.eu/resource/celex/{CELEX}`; send `Accept-Language: en` (without it Cellar answers 400), and percent-encode `(`, `)` and `/` in the CELEX.

## The 12 sectors

| Sector | Meaning | Descriptor letters (the second to fourth characters after the year) |
|---|---|---|
| **1** | Treaties | K ECSC, A Euratom, E EEC/EC/TFEU, M TEU, P Charter, L Lisbon, and one letter per accession treaty. Identifiers have **no fixed shape** (`12005SA051`, `12008M/PRO/07`). |
| **2** | International agreements | A agreements with non-member States or international organisations, D acts of bodies created by agreements, P acts of parliamentary bodies created by agreements, X other. Example `22026A00757` (5-digit number). |
| **3** | Legal acts | see the sector-3 table below. The largest sector. |
| **4** | Complementary legislation | A agreements between Member States, D decisions of the representatives of the governments of the Member States, X other acts in OJ L, Y other acts in OJ C, Z complementary legislation. |
| **5** | Preparatory documents | see the sector-5 table below. |
| **6** | EU case-law | CJ judgment, CO order, CC Advocate General opinion (Court of Justice); TJ, TO, TC (General Court); FJ, FO, FT (Civil Service Tribunal); CN/TN/FN new case notice; CA/TA/FA judgment notice; CB/TB/FB order notice. The number is the case number: `62012CJ0320` = case C-320/12; `62004TJ0201` = case T-201/04. |
| **7** | National transposition measures | L measures transposing directives, F measures transposing framework decisions. Same number as the act, sector 3 becomes 7, then a 3-letter country code and `_` and a sequence (`72014L0040FRA_240395`). |
| **8** | National case-law | descriptor is the country (BE, BG, CZ, DK, DE, EE, IE, EL, ES, FR, HR, IT, CY, LV, LT, LU, HU, MT, NL, AT, PL, PT, RO, SI, SK, FI, SE, UK, CH, IS, NO, XX = other courts, EFTA Court, ECtHR). Observed shape `82003PT1111(51)`. |
| **9** | Parliamentary questions | E written, H question time, O oral. Numbers have 6 digits: `91980E001013`. |
| **0** | Consolidated texts | non-official documents combining an act with its amendments and corrections; the basic act's number with sector 0 and a date suffix. |
| **C** | OJ C series | non-analysed notices and announcements, numbered by OJ C number: `C/YYYY/` + 5 digits starting with 0. |
| **E** | EFTA documents | A agreements between EFTA States, C acts of the EFTA Surveillance Authority, G acts of the EFTA Standing Committee, J decisions, orders and opinions of the EFTA Court, P pending EFTA Court cases, X information and communications. Example `E2016C0186`. |

### Sector 3 descriptors (legal acts)
A opinion, B budget, C declaration, D decision (with or without addressee), E CFSP common position / joint action / common strategy (pre-Lisbon), F police and judicial cooperation in criminal matters (pre-Lisbon), G resolution, H recommendation, J non-opposition to a joint venture, K ECSC recommendation, **L directive**, M non-opposition to a concentration, O ECB guideline, Q institutional arrangements (rules of procedure, internal agreements), **R regulation**, S ECSC decision of general interest, X other documents in OJ L (or before 1967), Y other documents in OJ C.

### Sector 5 descriptors (preparatory documents), by author
- **Commission**: **PC** COM legislative proposal and related documents, **DC** other COM documents (green and white papers, communications, reports), JC JOIN documents, SC SEC and SWD documents, EC/FC/GC codified proposals (regulations / directives / decisions), M merger control, AT antitrust, AS State aid, DMA, DSA, XC other. A longer number is normal: `52026XC01937`.
- **Council and Member States**: AG Council positions and statement of reasons, KG ECSC assent, IG Member State initiatives, XG other.
- **European Parliament**: AP legislative resolutions, BP budget, IP other resolutions and declarations, DP internal decisions, XP other.
- **Court of Auditors**: AA opinions, TA reports, SA special reports, XA other. **ECB**: AB opinions, HB recommendations, XB other.
- **EESC**: AE opinions on consultation, IE own-initiative opinions, AC opinions, XE other. **Committee of the Regions**: AR opinions on consultation, IR own-initiative opinions, XR other. **ECSC Committee**: AK, XK. **Other organs**: XX.

## Suffixes seen in practice
Checked against Cellar's own CELEX field on 13 Oct 2026 (hundreds of identifiers per sector) and against the 32,383 CELEX held in `eu_laws`:
- **`R(xx)` corrigendum**: `32000R1602R(05)`, `52008DC0782R(01)`. The source table says every document except sectors 0 and 7 can have one.
- **`(nn)`**: a further document filed under the same year, descriptor and number, e.g. `32014H0729(21)`, `22009A0619(01)`. Both suffixes can combine: `22009A0619(01)R(01)`. Treat the whole string as the identifier.
- **`-YYYYMMDD`** on sector 0: each date is a separate consolidated version of the same act.
- **`_SUM` / `_INF`** on sector 6: summary or information notice of a judgment or order (`62023CJ0294_SUM`).
- **5-digit numbers** exist in sectors 2, 3 and 5 (`22026A00757`, `32023D00161`); sector 9 has 6.
- In `eu_laws`, 29,408 of 32,383 stored CELEX are the plain 4-digit shape; about 3,000 carry a suffix or a longer number. A pattern that only knows `[1-9]\d{4}[A-Z]{1,2}\d{4}` silently drops them.

## COM to CELEX (the most common conversion)
`COM(2024) 206 final` becomes `52024PC0206` (proposal) or `52024DC0206` (communication). The verifier tries PC first, then DC, and keeps the one that resolves. JOIN documents are `JC`, SWD and SEC are `SC`.

## How Brubru uses CELEX
| Layer | Use |
|---|---|
| Knowledge guides | every QUICK FACTS block cites the anchor act's CELEX |
| `eu_laws` | the corpus LEG_2026-10: 34,309 distinct laws described (27,103 with text) / 59,010 OJ publications described (30,246 with text) / 64,844 translatable XML files; each OJ publication folder carries exactly one CELEX in its metadata (`tree_non_inferred.rdf`) |
| Citation verifier (`services/citation_verifier.py`) | extracts every CELEX shape above from a chat answer and checks it; used by the chat log and the public verify-citation endpoint |
| Catalan corpus | Formex V4 files in `docs/LEG_2026-10/`; output `frontend/public/legislacio-ue-catala/{celex}/index.html` |
| MCP `search_eu_legislation` | returns CELEX, title, document type |

### How the verifier checks a CELEX
1. Cellar with `Accept: application/xhtml+xml` and `Accept-Language: en`. 200 = ok, 404 = not conclusive.
2. **Then Cellar with a wildcard Accept**: 303 or 406 = the identifier exists but has no XHTML (most acts of the 1980s and 1990s, many consolidated texts, sectors 7 to 9); 404 = unknown to Cellar. Checked 13 Oct 2026: 15 impossible numbers across the sectors all return 404, and real ones return 200, 303 or 406.
3. EUR-Lex `HEAD` as a last resort (EUR-Lex often answers 202, a bot challenge, which means "unknown", never "broken").
4. Cache in `citation_verifications` (30 days ok, 24 hours broken, 1 hour unknown).

## Adjacent identifiers (not CELEX)
OJ reference (`OJ L 169, 25.6.2024, p. 1`), OEIL procedure (`2021/0106(COD)`), COM number, PE number (EP internal), A-/T-/B- numbers (EP plenary documents), SEC/SWD/C/IP/SPEECH (Commission internal), ELI (a URI, see `eli_european_legislation_identifier.md`), ECLI (case law, see `ecli_european_case_law_identifier.md`).

## Answer rule
When citing a CELEX, give both forms: `Regulation (EU) 2024/1689 (CELEX 32024R1689)`. Never say "search EUR-Lex yourself".

## Cross-references
- `finding_and_citing_eu_law.md`: where EU law lives and how to cite it
- `eli_european_legislation_identifier.md`: the ELI permalink (maps 1:1 to a CELEX)
- `eurovoc_thesaurus.md`: the subject concepts attached to each CELEX
- `ecli_european_case_law_identifier.md`: case-law identifier
- `official_journal_explained.md`: act-by-act publication since 1 Oct 2023
- `eu_legislative_procedures_explained.md`: CELEX versus OEIL procedure numbers
- `docs/api/eu_legal_data_access.md`: engineering reference (CDM, access paths)
- CLAUDE.md "Canonical Numbers of the EU Legal Corpus"
