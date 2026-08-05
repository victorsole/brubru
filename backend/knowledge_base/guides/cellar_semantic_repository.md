# Cellar: the Publications Office's Common Semantic Repository

## QUICK FACTS
- **What it is**: **Cellar** is the common data repository of the **Publications Office of the European Union (OP)**. It is the RDF triple store that holds the metadata and digital content behind EUR-Lex, the Official Journal, EU Open Data and the EU Vocabularies. When Brubru or any other tool fetches an EU law programmatically, it is almost always talking to Cellar under the hood, even where the user-facing surface says "EUR-Lex".
- **Underlying technology**: an OpenLink Virtuoso RDF triple store, holding several million work entries, each with a stable UUID-based Cellar identifier, exposed as Linked Open Data.
- **SPARQL endpoint**: `https://publications.europa.eu/webapi/rdf/sparql` (SPARQL 1.1, GET or POST, `Accept: application/sparql-results+json` for JSON). Public, no registration required. Query timeout around 60 seconds, so always use `LIMIT`/`OFFSET`.
- **Content-negotiation base URI**: `https://publications.europa.eu/resource/celex/<celex>` (also works with `cellar/<uuid>` and `eli/...`). Send an `Accept` header (`application/xhtml+xml`, `application/pdf`, `application/xml;notice=branch`, `application/zip;mtype=fmx4`, …) and Cellar returns, or redirects to, the matching manifestation.
- **Ontology**: the **Common Data Model (CDM)**, a FRBR-based (Work-Expression-Manifestation-Item, "WEMI") ontology describing over 200 document types across the Official Journal, case law, consolidated legislation and preparatory acts, plus AGENT, DOSSIER and EVENT entities. Full class/property list at the Metadata Registry (MDR): `https://op.europa.eu/en/web/eu-vocabularies/cdm`.
- **Who runs it**: the Publications Office of the European Union (OP), the same body that runs EUR-Lex, the Official Journal, TED and the EU Vocabularies.
- **Access without registration**: SPARQL endpoint, REST content-negotiation endpoint, RSS/Atom feeds for new/updated publications, and full bulk downloads are all open and free.
- **Official documentation hub**: `https://op.europa.eu/en/web/cellar` (Cellar section of the OP's EU Vocabularies portal).
- **Why it matters to Brubru**: `services/api_clients/cellar_sparql_client.py` queries the SPARQL endpoint directly (CELEX to ELI resolution, EuroVoc lookups, authority-table decoding); `services/comparator/structure_extractor.py` and `services/discovery/cellar_helpers.py` use the content-negotiation endpoint to fetch article/recital text, including the PDF fallback for proposals. See `reference_eurlex_waf_and_join.md` in project memory for the join pattern (CELEX to ELI to procedure to EuroVoc in one SPARQL round trip).

## What Cellar is, in plain terms

EUR-Lex, the Official Journal portal, data.europa.eu and the EU Vocabularies website are all **front-end presentations**. The actual documents and their metadata (title, date, author institution, legal basis, in-force status, EuroVoc subject terms, relationships to other acts) live in one back-end system: Cellar. Cellar stores this as RDF triples (subject-predicate-object statements), so a fact like "Regulation (EU) 2016/679 was adopted by the European Parliament and the Council on 27 April 2016" is not a database row but a graph edge that can be queried, combined and reasoned over alongside thousands of other such edges.

This matters practically: any question that requires combining two pieces of EU legal metadata (e.g. "which regulations from DG GROW were adopted since 2023 that reference EuroVoc concept 'consumer protection'") is, at root, a SPARQL query over Cellar, whether or not the tool asking it calls itself EUR-Lex, an EU Open Data client, or Brubru's own comparator service.

## The SPARQL endpoint

- **URL**: `https://publications.europa.eu/webapi/rdf/sparql`
- **Protocol**: SPARQL 1.1. GET with `query=<url-encoded SPARQL>`, or POST with `application/x-www-form-urlencoded` body.
- **Output negotiation**: set `Accept` to `application/sparql-results+json`, `application/sparql-results+xml`, or `text/csv`.
- **Interactive editor**: the same URL, opened in a browser, serves an OpenLink Virtuoso visual SPARQL query editor for exploratory querying.
- **Typical use in Brubru**: resolving a CELEX number to its ELI, EuroVoc descriptors, corporate-body author, in-force status, and related/amending acts, all in a single query against the CDM graph. `cellar_sparql_client.py` builds these queries against `RESOURCE_TYPE_AUTHORITY` (`http://publications.europa.eu/resource/authority/resource-type/`) and the `http://publications.europa.eu/resource/authority/language/` authority table for language filters.
- **Practical limits**: no authentication required, but queries time out around 60 seconds and unfiltered full-graph scans are the most common cause. Always scope by CELEX, ELI or a specific authority-table value; paginate with `LIMIT`/`OFFSET`.

## Content negotiation: fetching a document directly

Cellar's REST-style dissemination interface lets you dereference a document identifier and get back whichever representation you ask for, via the standard HTTP `Accept` header, rather than a bespoke query parameter for every format.

**Base pattern:**
```
GET https://publications.europa.eu/resource/celex/<celex>
Accept: <media type>
```

Common `Accept` values:
- `application/xhtml+xml`: HTML text of the act (what EUR-Lex's own reading view uses)
- `application/pdf`: PDF rendering
- `application/xml;notice=branch`: the branch metadata notice (what EUR-Lex's document-information page displays)
- `application/xml;notice=tree`: the fuller object-tree metadata notice
- `application/zip;mtype=fmx4`: Formex XML (the structured markup format used for the OJ and the acquis bulk exports; see `celex_number_format`)
- `application/rdf+xml` (default if no `Accept` is set and the identifier resolves to a WEMI object): raw RDF metadata

You can also dereference by Cellar UUID (`/resource/cellar/<uuid>`) or by ELI (`/resource/eli/...`; see `eli_european_legislation_identifier`), and add `Accept-Language: eng` (three-letter codes) to pick a language version.

### HTTP 300 Multiple Choices and `DOC_1`

Some Cellar manifestations have **more than one data stream** (for example, several PDF renditions, or a document split across annex files). In that case a `GET` returns **HTTP 300 Multiple Choices** with an XHTML body listing the alternative URIs, ordered by preference. The convention in scraping code (including Brubru's) is to take the **first listed alternative**, commonly labelled `DOC_1`, as the primary document. This is the standard fallback pattern: request the resource, detect a 300, grep the response body for the first `DOC_1` link, then re-request that specific URI.

### Why proposals are often PDF-only

Adopted legislation (regulations, directives, decisions once published in the OJ) almost always has a clean XHTML manifestation in Cellar. **Commission proposals and other preparatory acts frequently do not.** Requesting `Accept: application/xhtml+xml` for a proposal CELEX (types like `PC`, `DC`, `JC`) often returns **HTTP 404**, because the Publications Office only received a PDF rendition at that stage of the legislative process. The reliable fallback, used in `services/comparator/structure_extractor.py`, is:
1. Request the CELEX resource with `Accept: application/pdf`.
2. Follow the resulting HTTP 300 multi-choice response and take the `DOC_1` link.
3. Fetch that PDF directly and parse it with a PDF library (Brubru uses `pypdf`), extracting article/recital counts via regex over the extracted text.

Also note: `EurlexFetcher.CELEX_PATTERN`-style regexes built for adopted acts (single letter in the type position, e.g. `R`/`L`/`D`) will silently reject proposal CELEX numbers, which carry **two letters** (`PC`, `DC`, `JC`). Widen the pattern or bypass the fetcher and query Cellar directly when working with proposals.

## The Common Data Model (CDM)

The CDM is the ontology that describes every entity Cellar stores. Its core is the **FRBR/WEMI hierarchy**:
- **Work**: the abstract intellectual creation (e.g. "Regulation (EU) 2016/679" as a concept, independent of language or format)
- **Expression**: a specific language realisation of the work (the English text, the French text, …)
- **Manifestation**: a specific physical/digital embodiment of an expression (the XHTML rendering, the PDF, the Formex XML)
- **Item**: an individual copy/instance of a manifestation

Alongside WEMI, the CDM adds **Agent** (the institutions, bodies and individuals responsible for a document), **Dossier** (a grouping of related documents, such as a legislative procedure file) and **Event** (a dated occurrence in a document's lifecycle, e.g. adoption, signature, entry into force). Together these let Cellar answer questions like "who authored this act, when did it enter into force, and what procedure file does it belong to" as graph traversals rather than bespoke lookups. The full class and property list is published at the Metadata Registry (MDR), reachable from `https://op.europa.eu/en/web/eu-vocabularies/cdm`.

The CDM is being progressively aligned with **ELI/ELI-DL** (the European Legislation Identifier ontology; see `eli_european_legislation_identifier`) as part of the European Legal Space / EU Law Tracker initiative, so that data supplied by other portals (like the European Parliament's Open Data Portal) can be ingested into Cellar on a shared semantic footing.

## Authority tables

Cellar's metadata makes heavy use of **controlled vocabularies (Named Authority Lists, NALs)** rather than free text, so that the same concept is represented identically regardless of source language. Key authority tables relevant to legal research:
- **Resource type**: `http://publications.europa.eu/resource/authority/resource-type/` (e.g. `REG` for regulation, `DIR` for directive, `SUMMARY_LEGISLATION` for EUR-Lex legislative summaries)
- **Language**: `http://publications.europa.eu/resource/authority/language/` (three-letter codes, e.g. `ENG`, `FRA`)
- **Corporate bodies**: the authors of documents (European Parliament, Council, individual Commission DGs, agencies)
- **EuroVoc**: the multilingual thesaurus used to tag subject matter (see `eurovoc_thesaurus`); every act's EuroVoc descriptors are attached as CDM triples and are how EUR-Lex's own subject browsing works
- **File types**: distinguishes PDF, XHTML, Formex XML, DOC and other manifestation formats

These authority tables are themselves published as Linked Open Data and are queryable via the same SPARQL endpoint, which is what lets a single Cellar query decode a numeric or acronym code into a human-readable label in any of the EU's official languages.

## ELI, CELEX, and how Cellar ties them together

Cellar is the join point between the EU's two main legal identifier systems:
- **CELEX** (`celex_number_format`) is the Publications Office's internal catalogue key (e.g. `32016R0679`), independent of any legislative-procedure numbering.
- **ELI** (`eli_european_legislation_identifier`) is the dereferenceable, citable HTTP URI (e.g. `http://data.europa.eu/eli/reg/2016/679/oj`).

A single Cellar SPARQL query resolves CELEX to ELI (`cdm:resource_legal_eli`), and from there to EuroVoc descriptors, procedure references, and amendment relationships, all in one round trip. Brubru's own guidance is explicit: **never derive a CELEX number from an OEIL/procedure number or vice versa** (they are independent counters), and never derive an ELI by pattern-guessing when Cellar can be queried directly.

## REST APIs and bulk downloads

Beyond the SPARQL endpoint and single-document content negotiation, Cellar offers:
- **RSS and Atom feeds** announcing new or updated publications, so downstream systems can poll for changes rather than re-crawling.
- **Bulk download** of whole categories of content (for example, the full Formex XML acquis dump), which is how large-scale corpora such as the Publications Office's Nov 2025 bulk export (8,710 laws / 28,513 OJ publications / 61,219 translatable XML files, Brubru's canonical numbers for the EU legal corpus) are distributed and consumed.
- **Web services (SOAP)** for EUR-Lex-specific search, a separate, registration-required interface layered on top of the same underlying Cellar content, primarily used for keyword search rather than metadata graph queries.

## Why it matters to a policy professional

Most policy professionals never touch Cellar directly; they use EUR-Lex, the Official Journal, or a downstream tool like Brubru. But understanding that Cellar exists explains several things that otherwise look like inconsistencies:
- Why some EUR-Lex documents load instantly as clean web pages while others (typically Commission proposals) only offer a PDF: it reflects what manifestation was deposited in Cellar, not a EUR-Lex limitation.
- Why the "same" act can be cited with several different-looking URLs (a `legal-content` EUR-Lex URL, a `data.europa.eu/eli/...` URL, a raw `publications.europa.eu/resource/celex/...` URL): they are all pointers into the same underlying Cellar record, just via different front doors.
- Why bulk EU legal datasets (used for compliance tooling, AI training corpora, or large-scale regulatory monitoring) are sourced from Cellar bulk exports or SPARQL rather than scraped from EUR-Lex's web pages: it is faster, more complete, and the intended machine-readable channel.

## Cross-references
- `eur_lex_portal`: the public-facing search and reading portal built on top of Cellar
- `eli_european_legislation_identifier`: the dereferenceable citation URI Cellar resolves CELEX numbers into
- `eurovoc_thesaurus`: the multilingual subject-matter vocabulary stored and queried as a Cellar authority table
- `eu_publications_office_and_open_data`: the institution that runs Cellar and its wider publication remit
- `data_europa_eu_open_data_portal`: the EU-wide open-data portal that shares SPARQL infrastructure conventions with Cellar
- `celex_number_format`: the catalogue identifier Cellar uses as its primary key for legal acts
