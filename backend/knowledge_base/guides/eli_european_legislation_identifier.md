# ELI — the European Legislation Identifier

## QUICK FACTS
- **What it is**: the **European Legislation Identifier (ELI)** is a standardised **HTTP URI** for a piece of legislation, readable by both humans and machines. It makes EU and national law accessible, exchangeable and reusable across borders.
- **Basic shape**: `http://data.europa.eu/eli/{type}/{year}/{number}/oj`. Example — GDPR: `http://data.europa.eu/eli/reg/2016/679/oj`.
- **Why Brubru cares**: ELI is the **stable, citable link** Brubru should emit instead of `eur-lex.europa.eu/legal-content/...` URLs. It dereferences to the act on EUR-Lex, survives the Official Journal's act-by-act change, and (without `/oj`) returns the latest **consolidated** version.
- **Relationship to CELEX**: every act has both. CELEX (`32016R0679`) is the Publications-Office catalogue key; ELI is the dereferenceable URI. A single Cellar SPARQL query returns the ELI for any CELEX (`cdm:resource_legal_eli`). See `celex_number_format.md` and `finding_and_citing_eu_law.md`.
- **Source spec**: https://eur-lex.europa.eu/eli-register/about.html (Publications Office); deployed voluntarily across EU + national publishers.

## The URI structure
```
http://data.europa.eu/eli/{typedoc}/{year}/{number}/oj
```
- **typedoc**: `reg` (regulation), `dir` (directive), `dec` (decision), with `_impl` / `_del` variants for implementing / delegated acts (`reg_impl`, `dir_del`, `dec_impl`, …).
- **year**: year of adoption.
- **number**: the act's natural number.
- **`/oj`**: points to the version as published in the Official Journal.

### Dereferencing behaviour
- With `/oj` → the act as published.
- **Drop `/oj`** → the latest **consolidated** version if one exists (e.g. `http://data.europa.eu/eli/dec/2009/496`), or a results list of the act plus unconsolidated amendments.
- Although the URI is on the `data.europa.eu` domain, the page returned is served from EUR-Lex.

### Language and format
```
http://data.europa.eu/eli/{typedoc}/{year}/{number}/oj/{three-letter-language}/{format}
```
Examples: Italian text `…/eli/reg/2013/666/oj/ita`; Dutch PDF `…/eli/reg/2024/1834/oj/nld/pdf`.

### Subdivisions
ELI extends to parts of an act: `https://eur-lex.europa.eu/eli/reg/2019/1241/art_2/oj` = Article 2 of Regulation (EU) 2019/1241 (citations, recitals, articles, annexes).

## Worked examples
| Act | ELI |
|---|---|
| GDPR — Regulation (EU) 2016/679 | `http://data.europa.eu/eli/reg/2016/679/oj` |
| Water Framework Directive 2000/60/EC | `http://data.europa.eu/eli/dir/2000/60/oj` |
| AI Act — Regulation (EU) 2024/1689 | `http://data.europa.eu/eli/reg/2024/1689/oj` |
| Decision 2009/496/EC (latest consolidated) | `http://data.europa.eu/eli/dec/2009/496` |

## How Brubru should use ELI
- **In chat citations and the daily brief**, link the ELI rather than a `legal-content` URL — it is stable and won't 404 behind the WAF.
- **To resolve CELEX → ELI live**, use `scripts/cellar_news_helper.py --xref {celex}` (returns the ELI from Cellar). Wired into `context_builder` so chat can verify/emit ELIs on demand.
- **Never fabricate an ELI**; derive it from the act's type/year/number or read it from Cellar. Same anti-hallucination discipline as CELEX (`feedback_negation_paradox_in_warnings.md`).

## Cross-references
- `finding_and_citing_eu_law.md` — the hub: where EU law lives and how to cite it
- `celex_number_format.md` — the CELEX identifier (the catalogue key ELI maps to)
- `ecli_european_case_law_identifier.md` — the case-law equivalent
- `official_journal_explained.md` — why ELI matters after the 1 Oct 2023 act-by-act change
- `docs/api/eu_legal_data_access.md` — engineering reference (CDM `resource_legal_eli`, the join graph)
