# Finding and Citing EU Law — How the EU Legal-Data System Works

## QUICK FACTS
- **What this is**: the practical map of *where EU law lives* and *how to cite it correctly*. EUR-Lex is the public **front-end**; the actual store is **Cellar**, the Publications Office's semantic repository (RDF/OWL, content in Formex XML). Everything is addressable by identifier.
- **The master key is CELEX** (see `celex_number_format.md`). Every other identifier — **ELI** (`eli_european_legislation_identifier.md`), **ECLI** (`ecli_european_case_law_identifier.md`), COM/JOIN/SWD numbers, OJ references, OEIL procedure refs — resolves back to a CELEX.
- **Never HTML-scrape `eur-lex.europa.eu`**: it returns **HTTP 202 + an empty body** to any non-browser client (a JavaScript-challenge WAF). For data, go through Cellar; for the rare prose page, use a headless browser. See `feedback_cellar_needs_accept_language.md`.
- **Emit ELI links in citations, not `legal-content` URLs**: ELI is a stable HTTP URI that dereferences to the consolidated version of an act and survives the Official Journal's act-by-act change (see `official_journal_explained.md`).
- **Source spec**: https://eur-lex.europa.eu/content/help/data-reuse/reuse-contents-eurlex-details.html (Publications Office). Full Brubru engineering reference: `docs/api/eu_legal_data_access.md`.
- **Why Brubru relies on it**: chat citations, the citation verifier, the `eu_laws` table (28,513 OJ publications), the Catalan corpus, and the public API all key off this system.

## Where EU law physically lives — Cellar
EUR-Lex displays documents, but they are stored in **Cellar**, modelled by the **Common Data Model (CDM)** ontology (`http://publications.europa.eu/ontology/cdm#`). Controlled values (country, language, treaty, corporate body, subject) come from the **EU Vocabularies authority tables** (see `eurovoc_thesaurus.md`). Cataloguing follows the **Legal Analysis Methodology (LAM)**.

## The four machine-readable ways in (no WAF)
| Path | Endpoint | Best for |
|---|---|---|
| **Cellar SPARQL** | `http://publications.europa.eu/webapi/rdf/sparql` | Querying all metadata + relationships between acts (the real query API) |
| **Cellar REST** | `https://publications.europa.eu/resource/celex/{CELEX}` | One document's notice + content; send **both** `Accept` and lowercase `Accept-Language` or it 400s |
| **Data dump** | `https://datadump.publications.europa.eu` | Bulk download of in-force sector-3 acts per language (EU Login) — origin of Brubru's `LEG_2025-11` corpus |
| **SOAP webservice** | registered; expert-query → XML | Full-text search; **10,000-result cap since 1 Jan 2026** — page or use Cellar/dump |

The **`data.europa.eu`** open-data portal (DCAT-AP) is a separate stack: Search API `/api/hub/search/`, SPARQL `/sparql`, Registry `/api/hub/repo/`.

## The join model — one CELEX returns everything
A single Cellar SPARQL query on a CELEX returns its **ELI**, its **Official Journal reference**, the **legislative procedure** that produced it, its **EuroVoc topics**, its **legal basis**, whether it is **in force**, and the acts it **repeals or cites**. So the relationships between EUR-Lex, OEIL and an act are derivable, not hand-curated. (Verified on GDPR, CELEX `32016R0679` → ELI `http://data.europa.eu/eli/reg/2016/679/oj`, 9 EuroVoc concepts, 33 cited works.)

## The permanent-link views (address any document deterministically)
Stem: `eur-lex.europa.eu/legal-content/{LANG}/{VIEW}/{FORMAT}/?uri={ID}`
- **Views**: `TXT` (text) · `ALL` (document info) · `HIS` (procedure) · `PIN` (internal procedure) · `NIM` (national transposition) · `LSU` (legislation summary) · `CASE`/`SUM` (case-law).
- **Formats**: default / `HTML` / `PDF` / `XML` (the XML notice is the machine-readable metadata record).

So from one CELEX, Brubru can construct the procedure view, the transposition view, the plain-language summary and the XML notice — without scraping.

## How to cite (the Brubru standard)
- **Legislation in chat**: `Regulation (EU) 2024/1689 (CELEX 32024R1689)` — human-readable form + canonical identifier.
- **Stable link**: prefer the ELI, e.g. `http://data.europa.eu/eli/reg/2024/1689/oj`.
- **Case-law**: ECLI, e.g. `ECLI:EU:C:2014:317`.
- **Commission documents**: `COM(2024) 206 final` (convertible to CELEX `52024PC0206`).

## What Brubru must never do
- Never invent a CELEX/ELI/ECLI. If a reference cannot be verified against Cellar or EUR-Lex HEAD, say so and route the user to the authoritative source. See the "NEVER INVENT IDENTIFIERS" rule in `ai_service.py` and `feedback_negation_paradox_in_warnings.md`.
- Never present a raw `legal-content` link as a guaranteed-working URL without verification (they 404 silently behind the WAF). Use the citation verifier / emit ELI.

## Cross-references
- `celex_number_format.md` — the CELEX identifier in full (12 sectors, descriptors, quirks)
- `eli_european_legislation_identifier.md` — the ELI permalink system
- `ecli_european_case_law_identifier.md` — the case-law identifier
- `official_journal_explained.md` — how EU law is published (act-by-act since 1 Oct 2023)
- `eu_legislative_procedures_explained.md` — ordinary / special / non-legislative procedures
- `eurovoc_thesaurus.md` — the EU subject vocabulary used to classify acts
- `docs/api/eu_legal_data_access.md` — the full engineering reference (access paths, identifiers, CDM join graph)
- `services/citation_verifier.py` — Cellar + EUR-Lex HEAD verification with DB cache
