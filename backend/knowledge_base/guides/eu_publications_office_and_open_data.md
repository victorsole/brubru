# The Publications Office & EU Open Data (data.europa.eu, EUR-Lex, TED, CORDIS)

## QUICK FACTS
- **What this is**: the **Publications Office of the European Union (OP)** — an **interinstitutional service** (it serves all EU institutions, it is not a Commission DG) — and the data/publication surfaces it runs. Verified by crawling every URL in `docs/api/api_op.md` (31 May 2026).
- **What OP runs**: the **Official Journal** + **EUR-Lex** (EU law); **data.europa.eu** (the official EU open-data portal); **TED** (EU tenders); **CORDIS** (EU research projects); **EU WhoisWho** (the official directory of EU institutions & personnel); **EU Vocabularies** (authority tables, ontologies, EuroVoc); the **EU Web Archive**; and general EU publications.
- **The machine-readable backbone**: OP is where Brubru's legal/data joins resolve — the **corporate-body authority codes**, **EuroVoc**, **ELI/ECLI**, **Cellar**, and the **data.europa.eu SPARQL** endpoint all live here. See `eu_legal_data_access.md`, `eurovoc_thesaurus.md`, `finding_and_citing_eu_law.md`.
- **Source**: `op.europa.eu/en/home` + `data.europa.eu` + `ted.europa.eu` + `cordis.europa.eu` (all crawled). Engineering reference: `docs/api/eu_legal_data_access.md`.

## OP is interinstitutional (not a Commission DG)
The Publications Office publishes for **all** the EU institutions and bodies. Its WhoisWho directory lists them: the European Parliament, European Council, Council, Commission, Court of Justice (CURIA), ECB, Court of Auditors (ECA), EEAS, EESC, Committee of the Regions (CoR), EIB, EIF, the Ombudsman, the EDPS and the agencies. (Do not call OP a "service department of the Commission" — it is interinstitutional.)

## data.europa.eu — the official EU open-data portal
"The official portal for European data." It aggregates open datasets from EU institutions, Member States and partners. Key surfaces (all verified):
- **Datasets** — search the combined catalogue (`/data/datasets`, `/data/combined`); filter by source type (e.g. geospatial), by **High-Value Datasets** (`?is_hvd=true`, the categories defined under the **Open Data Directive**), and by super-catalogue.
- **SPARQL** — a query endpoint at `data.europa.eu/data/sparql` for the portal's metadata (distinct from **Cellar's** SPARQL at `publications.europa.eu/webapi/rdf/sparql`, which serves the legal corpus — see `eu_legal_data_access.md`).
- **Search API** — `data.europa.eu/api/hub/search/` for programmatic dataset discovery.
- **Metadata Quality Assessment (MQA)** — `data.europa.eu/mqa`, a dashboard scoring catalogue metadata quality.
- **Data spaces** — **ELDS** (European Legal Data Space) and **PPDS** (Public Procurement Data Space).
- **Open Data Maturity** — an annual report benchmarking Member States (2025 edition live).
- Plus the **data.europa academy**, community, podcasts, data stories, studies, and a licensing assistant.

## ELDS — European Legal Data Space
`data.europa.eu/ELDS` — legal datasets for reuse, including **case-law** (`elds-caselaw`). It complements **EUR-Lex** content reuse (`eur-lex.europa.eu/content/help/data-reuse/...`) and the **ECLI** search engine on the e-Justice portal. The bulk **datadump** of the legal corpus is at `datadump.publications.europa.eu`.

## TED — Tenders Electronic Daily
`ted.europa.eu` — "the **Supplement to the Official Journal**", i.e. EU public-procurement notices (contract notices, awards). This is the procurement universe behind Brubru's **Tenderator**. Public-procurement landing + search is also exposed via `op.europa.eu/.../public-procurement`.

## CORDIS — EU research projects
`cordis.europa.eu` — the Community Research and Development Information Service: EU-funded **research projects** (Horizon Europe and predecessors), their results, reporting, news, thematic packs, and a **datalab**. Useful for research/innovation questions and for the funding/projects picture alongside `eu_commission_funding_programmes_map.md`.

## EU WhoisWho & EU Vocabularies
- **WhoisWho** (`op.europa.eu/.../who-is-who`) — the official directory of EU institutions & personnel; per-organisation pages are keyed by **corporate-body code** (`…/organization/-/organization/{CODE}`), the same codes that tag Commission news/publications/acts (see `eu_commission_transparency_and_college_agenda.md`). Per-institution directories are also published as PDFs (EP, Council, COM, CURIA, ECB, ECA, EEAS, EESC, CoR, EIB, EIF, Ombudsman, EDPS, agencies).
- **EU Vocabularies** (`op.europa.eu/web/eu-vocabularies`) — the authority tables (countries, corporate bodies, resource types…), **EuroVoc**, ontologies and the Common Data Model (CDM). See `eurovoc_thesaurus.md` and `reference_eu_vocabularies` (memory).

## How Brubru uses this
- **Chat / EU Law Comply / Canon**: OP is the source layer for EUR-Lex/Cellar, ELI/ECLI, EuroVoc and the corporate-body codes that join an institution to its acts.
- **Tenderator**: TED (procurement) + CORDIS (research projects) + the PPDS.
- **My EU Bubble / data**: data.europa.eu datasets, the SPARQL + search APIs, and High-Value Datasets are a rich, machine-readable feed.
- **Future opportunity (not built yet)**: the OP **general publications** and **data.europa.eu datasets** are high-quality, citable material the Chat knowledge base could ingest. Flagged for a dedicated future session — see memory `project_op_publications_chat_ingestion`.

## Cross-references
- `eu_legal_data_access.md` — EUR-Lex/Cellar engineering (the legal corpus)
- `finding_and_citing_eu_law.md` · `official_journal_explained.md` · `eurovoc_thesaurus.md`
- `eu_commission_transparency_and_college_agenda.md` — corporate-body codes + WhoisWho
- `eu_commission_funding_programmes_map.md` — funding programmes (CORDIS projects sit here)
- `docs/api/eu_legal_data_access.md` — the engineering reference
