# EUR-Lex: The Official Portal for EU Law

## QUICK FACTS
- **What it is**: `eur-lex.europa.eu` is the official, free public access point to European Union law: legislation, case-law, treaties and preparatory documents, in all 24 official EU languages. It is the front-end that most people mean when they say "I looked it up on EUR-Lex".
- **Who runs it**: the **Publications Office of the European Union**, an **interinstitutional service** that publishes on behalf of all EU institutions and bodies (it is not a Commission department). See `eu_publications_office_and_open_data.md`.
- **Origins**: EUR-Lex descends from **CELEX**, the internal legal-documentation database EU institutions used from the 1960s. A public web version went live in 1997, with full public access from 2001.
- **Key dates**: the electronic Official Journal (e-OJ) became the sole **authentic, legally binding** edition on **1 July 2013**; the Official Journal moved to **act-by-act publication** (each act its own numbered OJ document, no more collated issues) on **1 October 2023**; Irish reached full official-language status on 1 January 2022, completing the 24-language set.
- **Languages**: 24 official EU languages.
- **The master identifier**: the **CELEX number** (e.g. `32016R0679` for the GDPR). Structure: 1-digit sector + 4-digit year + 1-2 letter document-type code + 4-digit sequential number. Full sector and type-code tables: `celex_number_format.md`.
- **Direct-link pattern**: `https://eur-lex.europa.eu/legal-content/{LANG}/{VIEW}/?uri=CELEX:{celex}`: e.g. `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679`.
- **Machine-readable backbone**: **Cellar**, the Publications Office's semantic/RDF repository at `publications.europa.eu`, queryable via SPARQL at `https://publications.europa.eu/webapi/rdf/sparql`. Cellar is where CELEX, ELI and EuroVoc data actually live; EUR-Lex is the human-facing display of it.
- **Operational note**: `eur-lex.europa.eu` runs bot-detection that blocks plain HTTP scraping (curl, `requests`) with a JavaScript-challenge response rather than the page content. Brubru never scrapes EUR-Lex directly; it reads Cellar (SPARQL or the resource API) or, for the rare case a human-readable page is needed, uses a headless browser. See `finding_and_citing_eu_law.md`.
- **Source**: https://eur-lex.europa.eu/content/welcome/about.html (Publications Office "About EUR-Lex" page).

## What EUR-Lex holds
EUR-Lex is a single search interface over several document families, all cross-linked by identifier:
- **Treaties**: the founding and amending treaties (TEU, TFEU, Euratom, Charter of Fundamental Rights, accession treaties).
- **Legislation**: regulations, directives, decisions, recommendations and opinions adopted by EU institutions (CELEX Sector 3), plus **consolidated versions** showing a law as currently amended (Sector 0).
- **International agreements**: treaties and agreements between the EU and third countries or organisations (Sector 2).
- **Preparatory acts**: Commission proposals and communications (COM), joint communications (JOIN), staff working documents (SWD) and related documents that precede adoption (Sector 5). See `eu_preparatory_document_identifiers.md` for the full identifier map.
- **Case-law**: judgments, orders and Advocate General opinions of the Court of Justice of the European Union (Sector 6). Cross-reference `ecli_european_case_law_identifier.md` for how judgments are cited.
- **EFTA documents**: material from the European Free Trade Association and the EEA framework relevant to EU law (Sector 7 area).
- **National transposition measures**: the national laws Member States adopt to transpose directives, linked back to the directive they implement.
- **National case-law referencing EU law**: national court decisions that cite or apply EU law.
- **The Official Journal**: the authentic publication record itself (see below).
- **Summaries of EU legislation**: several thousand plain-language explainers of major acts, maintained by the Publications Office, useful as a starting point before reading the full legal text.

## Who runs it and how it fits together
EUR-Lex is operated by the Publications Office of the European Union, the same interinstitutional body that runs the Official Journal, the CORDIS research database, TED (public procurement) and the EU Vocabularies authority tables. It is not a Commission product: it serves the Parliament, the Council, the Court of Justice, the ECB and every other EU institution and agency equally. See `eu_publications_office_and_open_data.md` for the full map of what the Publications Office runs.

## The CELEX identifier (summary)
Every document on EUR-Lex carries a CELEX number: a language-independent identifier built from a sector digit (what kind of document), the year, a document-type code, and a sequential number. Example: GDPR, Regulation (EU) 2016/679, is CELEX `32016R0679` (sector 3 = legislation, 2016 = year, R = regulation, 0679 = sequence). The full 12-sector table, document-type letter codes for legislation/preparatory-acts/case-law, and the quirks Brubru has hit in practice are documented in `celex_number_format.md`; do not re-derive a CELEX from a procedure (OEIL) number or a COM number by pattern-matching, they are independent counters that must be looked up.

## CELEX versus ELI
CELEX is the Publications Office's internal catalogue key: a string, not a URL. The **European Legislation Identifier (ELI)**, introduced by Council Conclusions of 10 October 2012, is a dereferenceable HTTP URI built from the act's type, year and number (e.g. `http://data.europa.eu/eli/reg/2016/679/oj`) that resolves directly to the act on EUR-Lex and, without the `/oj` suffix, to its latest consolidated version. Every act on EUR-Lex has both identifiers; a single Cellar query on a CELEX returns the matching ELI. Brubru's own citation practice prefers emitting the ELI link because it is stable and survives the Official Journal's identifier changes; see `eli_european_legislation_identifier.md`.

## The Official Journal on EUR-Lex
The Official Journal (OJ) is what gives an act legal effect, and EUR-Lex is where it is published. It has two series: **L** (Legislation, binding acts) and **C** (Information and notices). The electronic edition became the sole authentic, legally binding version on 1 July 2013 (before that, the printed paper edition was authentic). On 1 October 2023 the Publications Office switched from collated issues (an "OJ L 169, 25.6.2024" style volume with a table of contents) to **act-by-act publication**, where every act is its own numbered, individually authentic OJ document. This changes both OJ reference formats and OJ-based URLs, and Brubru code that builds or parses OJ references branches on that date. Full detail: `official_journal_explained.md`.

## Document page views
A EUR-Lex document page is addressable at the URL stem `eur-lex.europa.eu/legal-content/{LANG}/{VIEW}/{FORMAT}/?uri={identifier}`, where `{identifier}` can be a CELEX number, an ELI, an ECLI, a COM/JOIN/SWD reference, or an OJ reference. The main views are:
- **TXT**: the document text (HTML by default; add `/PDF/` or `/XML/` in the format slot for other formats).
- **ALL**: the "document information" view, combining metadata, the text and every language edition in one place.
- **HIS**: the procedure-history view, cross-linking to the legislative procedure that produced the act (the same procedure tracked in OEIL, see `oeil_legislative_observatory.md`).
- **NIM**: national implementing/transposition measures for a directive.
- **LSU**: the plain-language legislation summary, when one exists.
- **CASE / SUM**: case-law views for judgments and their summaries.

On top of the view, a document page offers a **multilingual display** that shows up to three language versions side by side (useful for verifying a translation or checking a specific-language legal nuance), a link to the **ELI** permalink, and a link to the current **consolidated version** if the act has been amended since adoption.

## Legal analysis: legal basis, EuroVoc, relationships
Within the "document information" view, EUR-Lex surfaces what is generally described as the document's legal analysis: the **legal basis** (the treaty article or prior act that empowers the institution to adopt it), the **EuroVoc** subject classification attached to the document (see `eurovoc_thesaurus.md` for how this controlled vocabulary works), and its **relationships** with other acts, including what it amends, what amends it, what it repeals or is repealed by, and what it cites. This is the same relationship graph that Cellar exposes over SPARQL, so a chatbot or script does not need to parse the EUR-Lex page to get it: one Cellar query on a CELEX returns the legal basis, EuroVoc concepts, and cited/citing works together. See `finding_and_citing_eu_law.md` for the query pattern.

## Building a direct link
The reliable way to link to a specific document is by CELEX or ELI, not by search-result URL (search URLs are session-dependent and break). Pattern:
```
https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679
```
Swap `EN` for another two-letter language code to get that language's version; swap `TXT` for `ALL` to land on the metadata/all-languages view instead of the plain text. For a link that survives the Official Journal's identifier changes, prefer the ELI form instead: `http://data.europa.eu/eli/reg/2016/679/oj`.

## Machine-readable access: Cellar, and why scraping EUR-Lex directly does not work
EUR-Lex the website is a display layer. The actual data store is **Cellar**, the Publications Office's RDF repository modelled on the Common Data Model (an FRBR-based ontology), reachable by SPARQL at `https://publications.europa.eu/webapi/rdf/sparql` or by direct resource fetch at `https://publications.europa.eu/resource/celex/{CELEX}`. Any programmatic use of EUR-Lex content (retrieving text, checking whether a CELEX exists, pulling EuroVoc tags or relationships) should go through Cellar, not through scraping `eur-lex.europa.eu` pages: the website runs bot detection that returns a JavaScript-challenge response instead of content to non-browser clients, which silently breaks naive `curl`/`requests`-based scrapers. Brubru's own citation verifier and content pipelines are built around Cellar for this reason; see `finding_and_citing_eu_law.md` and `cellar_semantic_repository.md`.

## Why this matters to a policy professional
EUR-Lex is the primary-source anchor for any EU-law claim: a chat answer, a briefing note, or a position paper that cites "the GDPR" or "the AI Act" should resolve to a specific CELEX/ELI on EUR-Lex, not a paraphrase from press coverage. Knowing the identifier system means a policy professional can go from a Commission proposal (COM number) to the adopted act (CELEX/OJ reference) to its legal basis and EuroVoc classification to any national transposition, all through one linked system, without needing separate tools. The procedure-history (HIS) view is the bridge from "what the law says" to "how it got there", linking out to the OEIL Legislative Observatory record of the legislative procedure itself.

## Cross-references
- `celex_number_format.md`: the CELEX identifier in full (12 sectors, type-code tables, quirks)
- `eli_european_legislation_identifier.md`: the ELI permalink system and its URI structure
- `ecli_european_case_law_identifier.md`: the case-law identifier used alongside the Sector 6 CELEX
- `eurovoc_thesaurus.md`: the subject-classification vocabulary attached to every document
- `cellar_semantic_repository.md`: the RDF repository and SPARQL endpoint underlying EUR-Lex
- `eu_publications_office_and_open_data.md`: the interinstitutional body that runs EUR-Lex, the OJ, TED, CORDIS and more
- `oeil_legislative_observatory.md`: the legislative-procedure tracker the EUR-Lex "procedure" view links out to
- `official_journal_explained.md`: the OJ's L/C series and the 1 October 2023 act-by-act change
- `finding_and_citing_eu_law.md`: the practical hub: where EU law lives and how Brubru cites it
- `eu_preparatory_document_identifiers.md`: COM/JOIN/SWD/SEC/PE/ST identifiers before adoption
- `eu_legislative_procedures_explained.md`: how a proposal becomes law, and how CELEX differs from OEIL procedure numbering
