# COM / JOIN / SWD / SEC / PE / ST: EU preparatory document identifiers

## QUICK FACTS

- **Topic**: The six main EU preparatory and inter-institutional document identifier systems, used before and during the legislative process
- **Sector in CELEX**: Commission preparatory documents fall under **Sector 5** (prefix `5`); Council working documents use a separate `consil:` URI scheme in EUR-Lex with no sector-5 CELEX of their own
- **EUR-Lex linking guide**: https://eur-lex.europa.eu/content/help/data-reuse/linking.html
- **Related guides**: `celex_number_format`, `finding_and_citing_eu_law`, `eli_european_legislation_identifier`, `official_journal_explained`, `eu_legislative_procedures_explained`, `eu_jargon`

| Identifier | Issued by | What it is | EUR-Lex URL fragment | Sector 5 CELEX |
|---|---|---|---|---|
| **COM(YYYY) NNN final** | European Commission | Legislative proposal or policy communication adopted by the full College | `?uri=COM:YYYY:NNN:FIN` | `5YYYYPCNNNN` (proposal) / `5YYYYDCNNNN` (communication) |
| **JOIN(YYYY) NN final** | Commission + HR/VP | Joint Communication on foreign, security, or external-relations policy | `?uri=JOIN:YYYY:NN:FIN` | `5YYYYJCNNNN` |
| **SWD(YYYY) NNN final** | Commission services | Staff Working Document: impact assessments, evaluations, accompanying analyses (from 2012 onwards) | `?uri=SWD:YYYY:NNN:FIN` | `5YYYYSCNNNN` |
| **SEC(YYYY) NNN final** | Commission SG | Secretariat-General internal document (pre-2012; largely replaced by SWD after the 2011 Better Regulation reform) | `?uri=SEC:YYYY:NNN:FIN` | `5YYYYSCNNNN` |
| **PE NN YYYY REV 1** | Council/inter-inst. | Final act prepared for signature and Official Journal publication after a legislative procedure | `?uri=consil:PE_NN_YYYY_REV_1` | No sector-5 CELEX; maps to the adopted act's Sector 3 CELEX once signed and published |
| **ST NNNNN YYYY INIT** | Council General Secretariat | Preparatory Council working document: compromise text, progress report, delegations' positions | `?uri=consil:ST_NNNNN_YYYY_INIT` | No sector-5 CELEX; internal Council numbering |
| **Ares(YYYY)NNNNNNNN** | Commission (internal) | Document registered in the Commission's Ares system, used for inter-service consultations and written-procedure decisions | `?uri=PI_COM:Ares(YYYY)NNNNNNNN` | Not routinely accessible via EUR-Lex; limited subset published as `PI_COM` entries |

**Sample verified URLs (EUR-Lex returns 202 Accepted from CloudFront for all):**
- COM(2021) 206 final (AI Act proposal): https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=COM:2021:206:FIN
- SWD(2024) 106 final: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=SWD:2024:106:FIN

---

## How to read each identifier

### COM(YYYY) NNN final

The most common identifier Brubru users ask about. Structure:

```
COM ( 2024 ) 380 final
     year    seq  stage
```

- `YYYY`: year the document was registered and adopted
- `NNN`: sequential number within that year (not zero-padded in the human-readable form, but zero-padded to 4 digits in the CELEX)
- `final`: the text adopted by the College; earlier internal drafts circulate without "final"

The same COM number can refer to either a **proposal** (PC) or a **communication** (DC). Brubru's citation verifier tries PC first, then DC. A proposal introduces a legislative act; a communication is a policy statement or action plan.

**Example**: COM(2021) 206 final is the original AI Act proposal. Its CELEX is `52021PC0206`. The final adopted Regulation is a Sector 3 CELEX: `32024R1689`.

### JOIN(YYYY) NN final

Issued jointly by the Commission and the High Representative of the Union for Foreign Affairs and Security Policy. Used for strategic external-relations documents (neighbourhood policy, enlargement, geopolitical strategies).

**Example**: JOIN(2022) 18 final is the "EU External Engagement in a Changing World" communication. CELEX `52022JC0018`.

### SWD(YYYY) NNN final

Staff Working Documents are technical annexes that accompany COM documents. They are not legally binding and are not adopted by the College; they are produced by the relevant DG's staff. Three types appear frequently:

- **Impact Assessment**: analyses costs, benefits, and policy options before a proposal
- **Impact Assessment Board Opinion**: the Regulatory Scrutiny Board's review of the impact assessment
- **Executive Summary**: brief version of the impact assessment

SWD documents replaced SEC documents in 2012 after the Better Regulation reform. Both use `SC` as the CELEX type-code in Sector 5.

### SEC(YYYY) NNN final

Pre-2012 Commission internal documents. The Secretariat-General used SEC numbering for a wide range of documents including impact assessments, interpretative communications, and procedural documents. After 2012 the category split into SWD (technical) and C (Commission decisions by written procedure).

### PE NN YYYY REV 1

In the Council's document register, `PE` documents are the final texts of acts agreed by the co-legislators (Parliament and Council) and ready for formal signature before publication in the Official Journal. "REV 1" indicates the first revision of that document (corrections to the agreed text are versioned REV 1, REV 2, etc.).

This is an **inter-institutional document number** used at the signature stage, distinct from:
- the original COM proposal number
- the procedure number in the OEIL register (`YYYY/NNNN(COD)`)
- the final CELEX of the adopted act in Sector 3

**Example**: a Regulation agreed in codecision will have a PE number before it is signed at the Council Presidency offices and published in the OJ L series.

### ST NNNNN YYYY INIT

Council working documents produced by the General Secretariat during the legislative procedure. INIT = initial text; ADD 1, ADD 2 = addenda; REV 1, REV 2 = revised versions. These documents are the internal working papers of Council working parties, COREPER I and II, and the Council itself.

Council documents are searchable at the Council's public register: https://data.consilium.europa.eu/doc/document/ST-NNNNN-YYYY-INIT/EN/pdf

**Example**: ST 15454 2016 INIT is a Council working document from 2016. URL pattern: `?uri=consil:ST_15454_2016_INIT`

### Ares(YYYY)NNNNNNNN

The Ares system (Advanced Records System) is the Commission's internal document management system. Ares numbers appear in:
- inter-service consultation requests (`ISC Ares(YYYY)NNNNNNNN`)
- internal Commission notes cited in footnotes of impact assessments
- written-procedure Commission decisions (`PI_COM:Ares(YYYY)NNNNNNNN` on EUR-Lex)

Most Ares documents are internal; a subset is published on EUR-Lex under the `PI_COM:` URI prefix.

---

## Sector 5 CELEX prefix logic

The five-digit CELEX prefix for preparatory documents always starts with `5`:

```
Sector  Year   Type     Number
5       YYYY   PC/DC    NNNN   →  Proposal / Communication
5       YYYY   JC       NNNN   →  Joint Communication
5       YYYY   SC       NNNN   →  Staff / Secretariat document (SWD or SEC)
```

The type-code is always **two letters** for Sector 5 (unlike Sector 3 where one letter suffices for most acts). This is the most common source of confusion: `52024PC0380` (4 leading zeros + 3-digit number = 0380) not `52024PC380`.

**Zero-padding rule**: the sequence number is always 4 digits. COM(2024) 380 → `0380`, COM(2021) 206 → `0206`, COM(2023) 1 → `0001`.

Full type-code table for Sector 5:

| Code | Meaning |
|---|---|
| PC | Proposal from the Commission (legislative proposal) |
| DC | Communication from the Commission (non-legislative policy document) |
| JC | Joint Communication (Commission + HR/VP) |
| SC | Staff Working Document (SWD) or Secretariat document (SEC) |
| IP | Press release / information note |
| AE | Opinion of the European Economic and Social Committee |
| AR | Opinion of the Committee of the Regions |
| AB | Opinion of the European Central Bank |
| AA | Opinion of the Court of Auditors |
| IG | Inter-institutional agreement (preparatory) |

---

## How to look up a document when you only have the number

**Step 1: construct the EUR-Lex URL directly**

For a COM document:
```
https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=COM:YYYY:NNN:FIN
```
Replace `YYYY` with the year and `NNN` with the number (no zero-padding in the URL).

For a SWD document:
```
https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=SWD:YYYY:NNN:FIN
```

For a JOIN document:
```
https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=JOIN:YYYY:NN:FIN
```

**Step 2: try the CELEX form if the URI form fails**

Construct the Sector 5 CELEX (see zero-padding rule above) and use:
```
https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:5YYYYPCNNNN
```

**Step 3: use EUR-Lex full-text search**

Go to https://eur-lex.europa.eu/search-results.html and search the exact document reference string, e.g. `COM(2024) 380`.

**Step 4: for Council documents (ST, PE)**

Use the Council's public register at https://www.consilium.europa.eu/register/en/content/out?DOC_LANCD=EN&MEET_DATE=&MEET_NUM=&DOC_REF=ST+NNNNN+YYYY+INIT

---

## Reading the suffixes: FIN, INIT, REV, ADD

| Suffix | Meaning | Appears on |
|---|---|---|
| `final` / `FIN` | Adopted version; the official text submitted to the co-legislators | COM, JOIN, SWD, SEC |
| `INIT` | Initial version of a Council document at the start of deliberations | ST, PE |
| `REV 1`, `REV 2` | Revised version (corrections or updates to the text) | ST, PE, and sometimes COM |
| `ADD 1`, `ADD 2` | Addendum (supplementary material to the main document) | ST |
| `COR 1` | Corrigendum (error correction after adoption) | COM, Sector 3 adopted acts |

A Council working document may go through several iterations: ST 15454 2016 INIT → ST 15454 2016 REV 1 → ST 15454 2016 REV 2 as Member States negotiate.

---

## Common chat-query patterns and Brubru answers

**"What does COM(2024) 380 mean?"**
This is a Commission document numbered 380 in 2024. It is either a legislative proposal (PC type) or a communication (DC type). Full text: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=COM:2024:380:FIN. CELEX: `52024PC0380` (proposal) or `52024DC0380` (communication).

**"Where can I read SWD(2024) 106?"**
This is a Commission Staff Working Document. Full text: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=SWD:2024:106:FIN. CELEX: `52024SC0106`.

**"What is PE 45 2016 REV 1?"**
This is a Council inter-institutional document prepared for signature. URI: `?uri=consil:PE_45_2016_REV_1`. Once the act was signed and published in the OJ, it received a Sector 3 CELEX.

**"How do I find ST 15454 2016 INIT?"**
Council working document 15454 from 2016, initial version. URI: `?uri=consil:ST_15454_2016_INIT`. Direct PDF: https://data.consilium.europa.eu/doc/document/ST-15454-2016-INIT/EN/pdf

**"What is a JOIN document?"**
A Joint Communication issued jointly by the European Commission and the High Representative. Used for external-relations strategy documents. Same URL pattern as COM but uses `JOIN:` prefix.

**"What is an Ares document?"**
An internal Commission document registered in the Ares system. Most are internal; some inter-service consultation and written-procedure documents appear on EUR-Lex under `PI_COM:Ares(YYYY)NNNNNNNN`.

---

## The relationship between preparatory identifiers and the final act

A single legislative procedure generates multiple document identifiers at different stages:

```
COM(2021) 206 final         -- original proposal (Sector 5 PC CELEX)
   SWD(2021) 84 final       -- accompanying impact assessment (Sector 5 SC CELEX)
   ST 12345 2022 INIT       -- Council working document during negotiation
   PE 88 2024 REV 1         -- final agreed text at signature stage
Regulation (EU) 2024/1689   -- adopted act (Sector 3 CELEX: 32024R1689)
OJ L 2024/1689              -- Official Journal publication reference
```

The OEIL procedure number (`2021/0106(COD)`) links all these stages together in the EP's legislative observatory. It is independent of every CELEX number listed above.

---

## Cross-references

- `celex_number_format` -- full CELEX structure, all sectors, all type codes, validation rules
- `finding_and_citing_eu_law` -- where EU law lives (Cellar, EUR-Lex, OJ) and how to cite it
- `eli_european_legislation_identifier` -- the stable ELI permalink that maps 1:1 to a CELEX for adopted acts
- `official_journal_explained` -- how acts are published in the OJ L and C series
- `eu_legislative_procedures_explained` -- OEIL procedure numbers vs CELEX (independent systems)
- `eu_jargon` -- plain-language glossary of EU institutional abbreviations
