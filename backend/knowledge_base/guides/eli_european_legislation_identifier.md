# ELI — the European Legislation Identifier

## QUICK FACTS
- **What it is**: the **European Legislation Identifier (ELI)** is a standardised **HTTP URI** for a piece of legislation, readable by both humans and machines. It makes EU and national law accessible, exchangeable and reusable across borders.
- **Basic shape**: `http://data.europa.eu/eli/{type}/{year}/{number}/oj`. Example — GDPR: `http://data.europa.eu/eli/reg/2016/679/oj`.
- **Why Brubru cares**: ELI is the **stable, citable link** Brubru should emit instead of `eur-lex.europa.eu/legal-content/...` URLs. It dereferences to the act on EUR-Lex, survives the Official Journal's act-by-act change, and (without `/oj`) returns the latest **consolidated** version.
- **Relationship to CELEX**: every act has both. CELEX (`32016R0679`) is the Publications-Office catalogue key; ELI is the dereferenceable URI. A single Cellar SPARQL query returns the ELI for any CELEX (`cdm:resource_legal_eli`). See `celex_number_format.md` and `finding_and_citing_eu_law.md`.
- **Source spec**: https://eur-lex.europa.eu/eli-register/about.html (Publications Office); deployed voluntarily across EU + national publishers.
- **Four pillars** (ELI is built on these, which can be adopted together or one by one): **1 identification** (a URI), **2 description** (a metadata ontology following FRBR), **3 publication** (the metadata embedded in the page as RDFa or JSON-LD), **4 synchronisation** (an ELI sitemap and an Atom feed so others can fetch every identifier and be told about new ones). Older documents number them I to IV.
- **Sources read in full on 13 Oct 2026**: EUR-Lex "What is ELI?" (last updated 27 Jan 2026) https://eur-lex.europa.eu/eli-register/what_is_eli.html and the EU Vocabularies ELI page https://op.europa.eu/en/web/eu-vocabularies/eli.

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

## The four pillars in detail
1. **Identification**: every legal text gets a URI built from recommended template components (type, year, number, date, language, format...) that each publisher may arrange in the order it prefers. The URIs defined by the national official journals and by the Publications Office (the "ELI publishers") are global web identifiers, readable by humans and machines. On EUR-Lex the components are type, year, number and `/oj`.
2. **Description**: the **ELI ontology** (OWL) is a common data model for legislation metadata (type of act, date of adoption, jurisdiction, relations to other acts). It follows the **FRBR** principles (work, expression, manifestation). The reference files are the OWL file, a table of metadata elements, model diagrams, an alignment with the **schema.org** legal extension (OWL and XLSX) and release notes; all versions are on EU Vocabularies.
3. **Publication**: the metadata must be encoded in **RDFa** (W3C Recommendation of 14 October 2008) or **JSON-LD**. The EUR-Lex page names JSON-LD 1.1 (W3C Recommendation of 16 July 2020); the older EU Vocabularies page still names JSON-LD 1.0 (2014). Publishers may offer further serialisations. Because the metadata sits in the HTML page, a consumer can extract it from the page itself.
4. **Synchronisation**: a protocol in which each publisher provides an **ELI sitemap** (the list of all identifiers) and an **ELI Atom feed** (new identifiers), so users keep their data up to date and a central graph of ELI data from several countries can be built. The specification is "ELI Pillar 4".

Implementing all four, even gradually, is what gives ELI its full value.

## Extensions and tools
- **ELI-DL** (2021-2022): ELI for draft legislation, to follow legislative initiatives across the EU.
- **ELI-I (ELI-Impact)**: a data model for the impact of legislative acts: how an amendment changes the original text or the latest consolidated version, the analysis of that impact, and impacts from other sources such as court decisions.
- **schema.org**: an ELI extension to the schema.org vocabulary so search engines can process legislation.
- **ELI/XML**: an XSD encoding of ELI metadata with transformations to RDF/XML, RDFa header or HTML+RDFa; not a dissemination format.
- **Tools** (Publications Office): the **ELI Validator** (checks published ELI metadata and produces a report), the **ELI annotation tool** (free, open source), the **Pillar 4 helper** (command-line Java application that generates sitemaps and RSS feeds).
- **N-Lex** has an ELI-based search across national legislation websites.
- The Publications Office aligns the CDM ontology used by Cellar with ELI and ELI-DL for the EU Law Tracker (formerly the Joint Legislative Portal), so Cellar can be fed from the European Parliament Open Data Portal.

## ELI in the Brubru corpus
Measured on the LEG_2026-10 export (13 Oct 2026, the 30,246 OJ publication folders with text, out of 59,010 in the export): the `tree_non_inferred.rdf` of **29,275** folders (97%) mentions an `eli/<type>/<year>/<number>/oj` URI (143 mention more than one, so match the URI to the folder's own CELEX); every folder carries its own CELEX, and 30,244 carry EuroVoc concept URIs. The English title is the `expression_title` of the expression whose `expression_uses_language` is ENG; half of the files give the titles with no `xml:lang`, so match on the language resource, not the attribute. CELEX, ELI, title and EuroVoc can therefore be joined from the metadata alone, without a network call.

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
