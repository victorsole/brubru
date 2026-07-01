# EP Open Data Portal and developer API (data.europarl.europa.eu)

## QUICK FACTS
- **Portal URL:** https://data.europarl.europa.eu/en/home
- **Operator:** European Parliament (Data Solutions Unit under DG Presidency)
- **Purpose:** Machine-readable catalogue of all EP parliamentary work in open, reusable formats; primary data access surface for developers, researchers, and journalists
- **API base (REST, OpenAPI 3):** `https://data.europarl.europa.eu/api/v2`
- **Developer corner:** https://data.europarl.europa.eu/developer-corner
- **Swagger UI (live API docs):** https://data.europarl.europa.eu/developer-corner/opendata-api
- **Rate limit:** 500 requests per 5-minute window per endpoint; no API key or registration required
- **Formats:** JSON-LD (default), RDF/XML, Turtle (TTL), CSV; set via `Accept:` header
- **Data licence:** Creative Commons Attribution 4.0 International (CC BY 4.0); commercial use permitted, attribution required
- **Dataset families (11):** Plenary Session Documents, Procedures, Plenary Documents, Committee Documents, Texts Adopted, Questions and Answers, Meetings, MEPs, Speeches, Vote Results, Bodies
- **Dataset count:** over 1,300 datasets as of the July 2025 release (ELI-EP 3.2.0), growing continuously
- **Data model standards:** ELI-EP (documents and activities), ORG-EP (persons and bodies), SKOS-EP (controlled vocabularies), DCAT-EP (catalogue metadata), EPVOC (EP-specific ontology)
- **NOT the same as doceo:** doceo hosts the actual document files (PDFs, DOCX) at constructible references; this portal is the linked-data and metadata API layer
- **NOT the same as RegistreWeb:** RegistreWeb handles citizen requests for public access to documents under Regulation 1049/2001; this portal is a developer data interface
- **Brubru client:** `backend/services/api_clients/ep_open_data_client.py`; used for amendment discovery, MEP data, and procedure feeds
- **Release cadence:** major releases approximately twice yearly; latest is July 2025 (ELI-EP 3.2.0, new APIs, SHACL-EP application profile)
- **Cross-reference guides:** `ep_documents_and_open_data.md` (engineering map of all EP data surfaces), `data_europa_eu_open_data_portal.md` (EU-wide federated portal), `eu_publications_office_and_open_data.md` (ELI infrastructure), `finding_and_citing_eu_law.md` (CELEX, EUR-Lex)

---

## What data.europarl.europa.eu is

The EP Open Data Portal is the European Parliament's authoritative machine-readable window into its parliamentary work. Officially launched in January 2023, it introduced REST API version 2 in the March 2024 major release. By July 2025 (ELI-EP 3.2.0), it held over 1,300 datasets across 11 families.

The portal does not host rendered documents. PDFs and Word files live on doceo. What the portal provides is structured metadata and linked data about EP activities: who the MEPs are, which procedures are open, how votes resolved, what texts were adopted, and which speeches were delivered. Each record is expressed in linked-data formats (JSON-LD, RDF/XML, Turtle) following EP-specific application profiles built on W3C and EU standards.

The portal is entirely open. No registration, no API key, no OAuth flow. The only constraint is the rate limit of 500 requests per 5-minute window per endpoint.

The EP bureau adopted its corporate open-data rules in May 2025, formalising the CC BY 4.0 licence and the commitment to near-real-time publishing.

---

## The dataset taxonomy

The EP open data catalogue organises content into 11 families:

| Family | What it contains | Key use case |
|---|---|---|
| Plenary Session Documents | Official Journal, Minutes, Verbatim Reports, Reports, Amendments, Motions | Full plenary record per session |
| Procedures | EP-tracked procedure files and events within them | Legislative tracking |
| Plenary Documents | Reports (A-series), motions (B-series), joint motions (RC-) | Amendment drafting research |
| Committee Documents | Draft reports (PR), draft opinions (PA), committee amendments (AM) | Committee-stage monitoring |
| Texts Adopted | Adopted resolutions and legislative texts (P10_TA-series) | Position research and citations |
| Questions and Answers | Parliamentary questions, written questions, oral questions | Policy monitoring |
| Meetings | Plenary sittings, agendas, decisions, vote results | Calendar and vote feeds |
| MEPs | Current and historical MEP profiles, group membership, committee mandates | Contact and composition research |
| Speeches | Plenary debate speeches, written statements | Transcript-level research |
| Vote Results | Roll-call votes per MEP per sitting | Predictions, Position Analysis |
| Bodies | Committees, political groups, delegations, inter-groups | Structure and membership |

Each dataset is available in at least one of: JSON-LD, RDF/XML, Turtle, CSV. Not every format is offered for every dataset; consult the dataset detail page.

---

## Developer corner: REST endpoints

The primary programmatic access route is `https://data.europarl.europa.eu/api/v2`. Full Swagger UI documentation lives at the developer corner Swagger page listed in the QUICK FACTS. No authentication is required. Respect the rate limit by introducing a 0.7-second delay between requests (Brubru's client enforces this).

### MEPs

| Endpoint | Returns |
|---|---|
| `GET /meps` | All MEPs across all terms |
| `GET /meps/show-current` | Active MEPs for today's date (718 for EP10) |
| `GET /meps/{mep-id}` | Full profile for one MEP |
| `GET /meps/feed` | Incremental feed: MEPs published or updated within a `timeframe` |
| `GET /meps/show-incoming` | MEPs joining the current term |
| `GET /meps/show-outgoing` | MEPs leaving the current term |
| `GET /meps/show-homonyms` | MEPs sharing a surname in the current term |

The `parliamentary-term` parameter (integer 0 to 10) filters results to a specific term. EP10 started in July 2024.

### Meetings

| Endpoint | Returns |
|---|---|
| `GET /meetings` | List of plenary sittings |
| `GET /meetings/{sitting-id}` | Single sitting details |
| `GET /meetings/{sitting-id}/decisions` | All decisions taken in that sitting |
| `GET /meetings/{sitting-id}/foreseen-activities` | Planned agenda items |
| `GET /meetings/{sitting-id}/vote-results` | All vote results for that sitting |

### Procedures

| Endpoint | Returns |
|---|---|
| `GET /procedures` | All EP-tracked procedures |
| `GET /procedures/{process-id}` | Single procedure (e.g. `2021/0106(COD)`) |
| `GET /procedures/{process-id}/events` | Events within a procedure |
| `GET /procedures/{process-id}/events/{event-id}` | Single procedure event |
| `GET /procedures/feed` | Incremental feed of updated procedures |

Note: this endpoint covers the EP-side only. The Council's position on a dossier is not here. For the full inter-institutional procedure file, use OEIL at `oeil.europarl.europa.eu/oeil/en/procedure-file?reference=...`.

### Documents and adopted texts

| Endpoint | Returns |
|---|---|
| `GET /adopted-texts` | All EP adopted texts |
| `GET /adopted-texts/{doc-id}` | Single adopted text (e.g. `P10_TA(2025)0042`) |
| `GET /adopted-texts/feed` | Incremental feed |
| `GET /documents` | All EP documents (plenary and committee amendment lists) |
| `GET /documents/{identifier}` | Single document detail (nested JSON-LD structure) |
| `GET /committee-documents` | Committee-stage documents (PR, PA, AM) |
| `GET /committee-documents/{identifier}` | Single committee document detail |

The `/documents` endpoint does NOT support server-side work-type filtering. You must paginate (max 100 per page via `offset` and `limit`) and filter client-side. Brubru does this in `ep_open_data_client.py`.

### Speeches and bodies

| Endpoint | Returns |
|---|---|
| `GET /speeches` | Plenary speeches, debate speeches, written statements |
| `GET /speeches/{speech-id}` | Single speech or speech-related activity |
| `GET /corporate-bodies` | Committees, political groups, delegations |
| `GET /corporate-bodies/{body-id}` | Single body with membership |

---

## SPARQL and linked data formats

The EP Open Data Portal exposes its data as RDF following ELI-EP, ORG-EP, and SKOS-EP application profiles. Any resource can be retrieved as RDF/XML or Turtle by passing the appropriate `Accept:` header:

```
GET https://data.europarl.europa.eu/api/v2/meps/197539
Accept: text/turtle
```

A dedicated public SPARQL endpoint on data.europarl.europa.eu is not documented. For cross-institutional SPARQL queries joining EP data with Commission, Council, or other EU-body data, use the EU Open Data Portal SPARQL endpoint at `https://data.europa.eu/data/sparql`, which harvests and federates metadata from all EU institutions including the EP. See `data_europa_eu_open_data_portal.md`.

---

## Data models and ontologies

The EP open data follows a layered ontology stack:

- **EPVOC:** The EP-specific ontology defining classes and properties used across all EP application profiles.
- **ELI-EP (European Legislation Identifier, EP extension):** Covers documents and activities: adopted texts, plenary documents, procedures, meetings, speeches, votes, committee documents. Current version 3.2.0 (July 2025).
- **ORG-EP:** Covers persons (MEPs) and organisational bodies (committees, groups, delegations).
- **SKOS-EP:** Controlled vocabularies (term lists, document types, languages, taxonomies).
- **DCAT-EP:** Catalogue-level metadata standard extending DCAT-AP for the EP's own dataset catalogue.

The JSON-LD responses use a nested `is_realized_by` (Expression level) then `is_embodied_by` (Manifestation level, containing download URLs per language) structure reflecting the FRBR-inspired ELI hierarchy. When parsing: unwrap the `data` array first, then walk the expression-manifestation chain to reach title and download path for a specific language.

---

## Data licence

All data on the EP Open Data Portal is published under **Creative Commons Attribution 4.0 International (CC BY 4.0)**:
- Commercial use is permitted.
- Attribution to the European Parliament is required (cite the source dataset URL and the EP).
- No additional restrictions may be placed on re-users.

The bureau of the European Parliament adopted its corporate open-data rules in May 2025, formalising this policy across all EP datasets.

---

## Decision tree: which EP surface to use

This is the most common point of confusion for users and developers. Three EP data surfaces coexist with distinct roles:

| Need | Use | URL pattern |
|---|---|---|
| Structured data feed: MEP list, vote results, procedure status, for programmatic use | EP Open Data API | `data.europarl.europa.eu/api/v2` |
| Download the actual document file (PDF, DOCX) by EP reference | doceo | `europarl.europa.eu/doceo/document/{ref}_EN.pdf` |
| Assert a legal right of access to an EP document under Reg 1049/2001 | RegistreWeb | `europarl.europa.eu/RegistreWeb/` |
| Cross-institutional query spanning EP, Commission, Council in one SPARQL call | EU Open Data Portal SPARQL | `data.europa.eu/data/sparql` |

When a user asks "where can I download EP committee amendments?": the metadata and reference is on the Open Data API; the DOCX file is on doceo at `europarl.europa.eu/doceo/document/{ref}_EN.docx`.

See `ep_public_register_of_documents_registreweb.md` (planned sibling guide) for the full RegistreWeb workflow.

---

## Canonical example queries

### Example 1: List current EP10 MEPs with political group

```
GET https://data.europarl.europa.eu/api/v2/meps/show-current?parliamentary-term=10
Accept: application/ld+json
```

Response: JSON-LD array of MEP objects, each with `skos:notation` (MEP ID), `foaf:familyName`, `foaf:givenName`, `org:memberOf` (group and committee URIs). The current EP10 count is 718 (total elected), 718 active.

### Example 2: Vote results for a plenary sitting

```
GET https://data.europarl.europa.eu/api/v2/meetings/{sitting-id}/vote-results
Accept: application/ld+json
```

Replace `{sitting-id}` with the EP sitting identifier (pattern: `MTG-PL-YYYY-MM-DD`). Returns roll-call results per vote item with a MEP-level breakdown (for, against, abstain, did not vote).

### Example 3: Adopted text by reference

```
GET https://data.europarl.europa.eu/api/v2/adopted-texts/P10_TA(2025)0042
Accept: application/ld+json
```

Returns structured metadata. For the full document, follow the `is_embodied_by` URL in the response to the corresponding doceo PDF or HTML.

### Example 4: Plenary agenda (OJ-SYN) via doceo, not the Open Data API

The plenary session agenda (OJ-SYN) is a plenary session document. Its doceo reference is:
`OJ-10-{YYYY-MM-DD}-SYN_EN.html`

This is a **doceo** URL. The session metadata (sitting ID, decisions, vote results) is on the Open Data API. The rendered agenda HTML is on doceo. Use the API for machine-readable structure and doceo for the formatted document.

---

## How Brubru consumes EP open data

| EP endpoint | Brubru feature |
|---|---|
| `/adopted-texts`, `/meetings/{id}/vote-results` | Predictions, Position Analysis |
| `/procedures` + OEIL | Legislative Tracker, My Tracked Files |
| `/documents`, `/committee-documents` | Amendator (amendment discovery and PE-reference enrichment) |
| `/meps`, `/corporate-bodies` | Chat context: group membership, committee composition |
| `/speeches` | Transcripts feature: source index for plenary speech records |

The API client lives at `backend/services/api_clients/ep_open_data_client.py`. Key implementation notes:
- Sets `User-Agent: Brubru/1.0 (EU Policy Intelligence)` on every request.
- Requests `Accept: application/ld+json` by default.
- Enforces 0.7-second inter-request delay to stay within the 500 req / 5 min cap.
- Paginates `/documents` and `/committee-documents` with `offset` and `limit` (max 100 per page) and filters client-side for work type, since the API does not expose a server-side work-type filter parameter.

---

## Caveats and known limitations

**Data freshness.** The portal publishes "almost in real time" according to EP documentation, but freshness varies by dataset. Vote results for a plenary sitting typically appear within 24 to 48 hours. MEP mandate changes appear when formally processed (may lag nominations by days). Procedure feed entries reflect EP-side events only; for inter-institutional stage data OEIL is more complete.

**ID scheme multiplicity.** The EP uses at least three identifier schemes: OEIL procedure references (`2021/0106(COD)`), EP document references (`A10-0045/2025`, `P10_TA(2025)0042`, `PE753.448`), and internal API IDs (`MTG-PL-...`, numeric MEP IDs). These do not map trivially to each other. Never derive a CELEX number from an OEIL reference: they are independent counters. See `finding_and_citing_eu_law.md` and the CLAUDE.md rule on CELEX vs OEIL numbering.

**No server-side work-type filter on `/documents`.** The documents list endpoint lacks a `work_type` query parameter. A full amendment discovery run requires paginating through all results and filtering client-side. This can involve hundreds of API requests.

**JSON-LD is the most complete format.** RDF/XML and Turtle are available for many endpoints but may not cover all fields. CSV exports cover flat datasets (MEPs, votes) but lose the nested linked-data structure.

**OEIL is richer than `/procedures`.** The OEIL procedure files include inter-institutional stage data not available on the EP Open Data API. Use OEIL as the primary source for procedure tracking; use this API for vote results, MEP data, and document discovery.

**EP10 URL discipline.** All EP10 document references use `-10-` not `-9-`. Adopted texts are `P10_TA(YYYY)NNNN`. Reports are `A10-NNNN/YYYY`. On a 404, switch tool (Tavily, scraper output) rather than guessing a similar path.

---

## Reporting issues and contacting the EP data team

The portal includes a contact form at https://data.europarl.europa.eu/contact. Submit bug reports, dataset requests, and API access issues there.

Release notes for all API changes are published at https://data.europarl.europa.eu/release-notes. The July 2025 release is the latest (ELI-EP 3.2.0, SHACL-EP application profile, new APIs, `timeframe` parameter additions). A beta-tester programme exists for early access to new datasets; sign up via the "Be a beta tester" link on the portal homepage.

---

## Cross-references

- `ep_documents_and_open_data.md` -- engineering map of all EP data surfaces (API, doceo, OEIL, RegistreWeb, EPRS Think Tank); the companion reference to this guide
- `ep_public_register_of_documents_registreweb.md` -- RegistreWeb: citizens' right-of-access surface under Regulation 1049/2001 (planned sibling guide)
- `data_europa_eu_open_data_portal.md` -- the EU-wide open-data portal (data.europa.eu) which federates EP datasets with all other EU institutions; the SPARQL cross-institutional query surface
- `eu_publications_office_and_open_data.md` -- the Publications Office infrastructure that powers ELI and the EU's linked-data layer
- `finding_and_citing_eu_law.md` -- how to find and cite EU legislation on EUR-Lex; covers CELEX numbers referenced from EP procedure files
