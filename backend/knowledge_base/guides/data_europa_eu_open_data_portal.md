# data.europa.eu: the official EU open-data portal

## QUICK FACTS
- **URL:** https://data.europa.eu/en
- **Operator:** Publications Office of the European Union (on behalf of the European Commission)
- **Role:** Single authoritative catalogue for all open data published by EU institutions, bodies, agencies, and member-state national portals
- **Scale:** ~1.7 million datasets harvested from 80+ source catalogues (EU institutions + 27 national portals + regional catalogues)
- **Metadata standard:** DCAT-AP (Data Catalogue Vocabulary, Application Profile for European data portals), extended as DCAT-AP 3.0
- **Licence default:** Creative Commons Attribution 4.0 (CC BY 4.0) and variants; Open licence assistant at https://data.europa.eu/en/training/licensing-assistant
- **Search API:** https://data.europa.eu/api/hub/search/
- **SPARQL endpoint:** https://data.europa.eu/data/sparql (DCAT-AP metadata graph, queryable via SPARQL 1.1)
- **Metadata Quality Dashboard (MQA):** https://data.europa.eu/mqa
- **High-Value Datasets (HVD) filter:** https://data.europa.eu/data/datasets?is_hvd=true&locale=en
- **Sub-portals (Common European Data Spaces):** European Legal Data Space (ELDS), Public Procurement Data Space (PPDS), European Health Data Space (EHDS), Green Deal Data Space (GDS)
- **Data Provider Interface (DPI):** self-service harvesting registration for organisations publishing open data
- **Academy:** open-data training courses at https://data.europa.eu/en/academy
- **Brubru integration:** extract engine + scrapers consume data.europa.eu metadata and dataset endpoints; used for EU legislation corpus, procurement notices, and EuroVoc-enriched document harvesting

> For the Publications Office infrastructure that runs data.europa.eu, see `eu_publications_office_and_open_data.md`. For EuroVoc thematic classification used across catalogued datasets, see `eurovoc_thesaurus.md`. For the Cellar semantic repository underlying EU legal documents, see `cellar_semantic_repository.md` (planned). For the High-Value Datasets implementing regulation, see `eu_high_value_datasets_hvd_reg_2023_138.md` (planned). For sub-portal detail, see `eu_legal_data_space_elds.md` (planned), `eu_procurement_data_space_ppds_eforms.md` (planned), and `cordis_research_projects_database.md` (planned).

---

## What data.europa.eu is

data.europa.eu is the official open-data portal of the European Union. It was created by merging two predecessor portals: the EU Open Data Portal (run by the Publications Office since 2012) and the European Data Portal (run by the European Commission since 2015). The merger completed in 2021, producing a single point of access to EU institutional data and to harvested national catalogues across all 27 member states.

The portal does not host raw data files directly in most cases. Instead it publishes structured metadata records pointing to the original distribution URLs at the publishing organisation. The Publications Office maintains the catalogue infrastructure, quality tooling, and API layer; individual publishers retain custody of the underlying files.

Users of the portal include policy analysts seeking statistics, journalists investigating EU spending, researchers building machine-learning corpora, compliance professionals checking regulatory datasets, and developers integrating EU data into applications. Brubru itself is one such consumer.

---

## Coverage and harvesting model

The portal harvests from three tiers:

1. **EU institutional publishers:** European Commission (DGs and executive agencies), European Parliament, Council of the EU, Court of Justice, European Central Bank, Eurostat, EFSA, EMA, ECHA, EEA, and all other EU bodies. These are catalogued directly via the DPI or through scheduled OAI-PMH and DCAT-AP feeds.

2. **National open-data portals:** Each of the 27 member states provides a national catalogue federation endpoint. The portal harvests these on a rolling schedule, meaning some national records may lag by hours or days relative to the national portal's live state.

3. **Regional and thematic catalogues:** Selected sub-national catalogues (Flemish, Catalan, Scottish, etc.) and thematic registries (Copernicus, Inspire geospatial, TED procurement) feed into the aggregate.

Harvesting uses the DCAT-AP standard (see below). Records that fail validation appear in the MQA dashboard with remediation guidance rather than being suppressed entirely, preserving discoverability while signalling quality issues to publishers.

---

## DCAT-AP metadata standard

DCAT-AP (Data Catalogue Vocabulary Application Profile) is the EU-mandated interoperability standard for data catalogues. It is a constrained profile of the W3C DCAT recommendation, with EU-specific extensions.

Key DCAT-AP concepts relevant to querying data.europa.eu:

| Concept | DCAT-AP class | Practical meaning |
|---|---|---|
| Dataset | `dcat:Dataset` | The logical unit: a dataset has a title, description, theme, keywords, publisher, and one or more distributions |
| Distribution | `dcat:Distribution` | A specific format/download of the dataset (CSV, JSON, RDF, SPARQL, API endpoint) |
| Catalogue | `dcat:Catalog` | A collection of datasets from one publisher |
| Theme | `dcat:theme` | EuroVoc or EU Data Theme vocabulary URI |
| HVD category | `dcatap:hvdCategory` | High-Value Dataset category under Implementing Regulation 2023/138 |
| Licence | `dct:license` | Licence document URI, preferably from the EU vocabularies licence register |

DCAT-AP 3.0 (adopted 2023) adds native support for HVD categories, data services (API endpoints as first-class citizens), and improved provenance modelling. Publishers upgrading from DCAT-AP 2.1 must add `dcatap:hvdCategory` for any High-Value Dataset and expose API distributions as `dcat:DataService` nodes.

---

## Programmatic access: four surfaces

### 1. Search API

**Base URL:** `https://data.europa.eu/api/hub/search/`

The search API supports full-text search, filtering by theme, publisher, format, HVD flag, country, and date range. It returns JSON-LD responses following DCAT-AP.

Key parameters:

| Parameter | Example | Effect |
|---|---|---|
| `q` | `q=air+quality` | Full-text search across title, description, keywords |
| `filter` | `filter=country:BE` | Filter by country code |
| `filter` | `filter=is_hvd:true` | High-Value Datasets only |
| `filter` | `filter=format:CSV` | Distribution format |
| `filter` | `filter=publisher_name:eurostat` | Restrict to a publisher |
| `limit` | `limit=10` | Page size (max 100) |
| `page` | `page=2` | Pagination |
| `sort` | `sort=modified+desc` | Recency sorting |

Example request returning the 10 most-recently updated HVD datasets:

```
GET https://data.europa.eu/api/hub/search/?filter=is_hvd:true&sort=modified+desc&limit=10
```

### 2. SPARQL endpoint

**URL:** `https://data.europa.eu/data/sparql`

The SPARQL endpoint exposes the full DCAT-AP metadata graph. It supports SPARQL 1.1 SELECT, CONSTRUCT, ASK, and DESCRIBE. The named graph `<https://data.europa.eu/data/graphs/sparql>` contains the entire catalogue.

Useful query pattern to list all datasets from a given publisher by EuroVoc theme:

```sparql
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dct:  <http://purl.org/dc/terms/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>

SELECT ?dataset ?title ?modified WHERE {
  ?dataset a dcat:Dataset ;
           dct:title ?title ;
           dct:modified ?modified ;
           dct:publisher ?pub .
  ?pub foaf:name "Eurostat"@en .
  FILTER(LANG(?title) = "en")
}
ORDER BY DESC(?modified)
LIMIT 20
```

Combine with EuroVoc URIs (from `eurovoc_thesaurus.md`) via `dcat:theme` to retrieve thematically scoped datasets without keyword search.

### 3. Dataset-level endpoints

Each dataset record has a persistent URI of the form:

```
https://data.europa.eu/data/datasets/{dataset-id}
```

The dataset page lists all distributions with download URLs and format labels. Programmatic access follows DCAT-AP: fetch the dataset URI with `Accept: application/ld+json` or `Accept: application/rdf+xml` to retrieve structured metadata.

### 4. Bulk download and linked-data snapshots

The Publications Office publishes periodic full-catalogue dumps in N-Quads and Turtle format for offline processing. Links are available from the portal's developer documentation at `https://data.europa.eu/en/developer-corner`. These dumps are useful for building local indexes or training classifiers over the full metadata corpus without rate-limit concerns.

---

## Sub-portals: Common European Data Spaces

The European Data Strategy (2020) mandated sectoral data spaces. data.europa.eu hosts or links four thematic sub-portals with enhanced metadata, specific governance, and dedicated APIs:

### European Legal Data Space (ELDS)
Aggregates EU legal documents: OJ series L and C, ECLI case-law, CELEX corpus, ELI-tagged legislation. Powered by the Cellar semantic repository. See `eu_legal_data_space_elds.md` (planned) and `cellar_semantic_repository.md` (planned).

### Public Procurement Data Space (PPDS)
Integrates eForms notices from TED (Tenders Electronic Daily), contract award data, and spending datasets. Linked to Open Contracting Data Standard (OCDS) outputs. See `eu_procurement_data_space_ppds_eforms.md` (planned).

### European Health Data Space (EHDS)
Aggregates health statistics, clinical trial registries (EudraCT/CTIS), ECDC epidemiological datasets, and EMA medicine data. Governed under Regulation 2025/327.

### Green Deal Data Space (GDS)
Aggregates climate, biodiversity, and environmental datasets: Copernicus, EEA Air Quality Index, EU taxonomy-aligned corporate reporting, and Eurostat environment statistics.

---

## High-Value Datasets (HVD)

Implementing Regulation (EU) 2023/138 designates six categories of High-Value Datasets that public sector bodies across the EU must publish as open data, free of charge, in machine-readable format, with an API:

1. Geospatial
2. Earth observation and environment
3. Meteorological
4. Statistics
5. Companies and company ownership
6. Mobility

On data.europa.eu, HVD datasets carry the `is_hvd=true` flag and a `dcatap:hvdCategory` triple linking to the relevant category URI. The dedicated filter URL is:

`https://data.europa.eu/data/datasets?is_hvd=true&locale=en`

Key HVD sources on the portal include: Eurostat (statistics), Business Registers Interconnection System (BRIS, company data), Copernicus (earth observation), INSPIRE geoportal (geospatial), and national meteorological services.

For the full legal framework, see `eu_high_value_datasets_hvd_reg_2023_138.md` (planned).

---

## How Brubru uses data.europa.eu

Brubru's backend integrates with data.europa.eu at multiple points:

**Extract engine (`backend/services/`):** Harvests DCAT-AP metadata records from the search API to discover new EU datasets relevant to tracked policy areas. The extract engine applies EuroVoc thematic filters to scope retrieval to user-relevant domains.

**Scrapers (`backend/services/scrapers/`):** Several scrapers use distribution download URLs sourced from data.europa.eu records as their canonical fetch targets (e.g. Eurostat SDMX feeds, EEA spatial data, EFSA opinion registers). The portal acts as a stable indirection layer: if a publisher changes their CDN path, the DCAT-AP record is updated and the scraper can re-resolve via the dataset URI rather than hard-coding a file URL.

**EU legislation corpus:** The ELDS sub-portal's CELEX-indexed distributions are part of the extraction pipeline used to build and refresh Brubru's legislative coverage (see `eu_publications_office_and_open_data.md`).

**EuroVoc enrichment:** Dataset `dcat:theme` URIs from the catalogue feed into Brubru's EuroVoc-based topic classification (see `eurovoc_thesaurus.md`).

---

## Practical tips for users and developers

### Data Provider Interface (DPI)
Organisations wishing to publish data on data.europa.eu register through the DPI at `https://data.europa.eu/en/data-provider-interface`. The DPI accepts DCAT-AP feeds, OAI-PMH endpoints, and manual dataset registration. After validation, records appear in the catalogue within 24 hours. Useful for: national agencies, research institutions, NGOs publishing EU-funded project outputs.

### Metadata Quality Assessment (MQA)
The MQA dashboard at `https://data.europa.eu/mqa` scores every catalogued dataset across five dimensions: findability, accessibility, interoperability, reusability, and contextual information. Publishers receive automated alerts when scores drop. For users, the MQA score is a proxy for dataset reliability: datasets scoring above 300/405 are generally well-described with working download links.

### Open Licence Assistant
At `https://data.europa.eu/en/training/licensing-assistant`, the assistant helps publishers choose a compatible open licence and helps users confirm reuse rights for a given dataset.

### Academy
Free self-paced courses covering open-data publishing, DCAT-AP implementation, SPARQL basics, and data quality. Available at `https://data.europa.eu/en/academy`. Useful for staff at public bodies building data publication pipelines.

### Finding a dataset: recommended workflow
1. Use the search interface at `https://data.europa.eu/en` with plain-language keywords.
2. Narrow by publisher (Eurostat, EEA, Commission DG) and format (CSV, JSON, RDF, SPARQL).
3. Apply the HVD filter if the use case falls into one of the six HVD categories.
4. For structured retrieval, use the SPARQL endpoint with an EuroVoc theme URI to scope by policy area.
5. Check the MQA score before building a pipeline dependency on a dataset.
6. Use the persistent dataset URI (not the distribution download URL) as the canonical reference, since download URLs can change.

---

## Related guides

- `eu_publications_office_and_open_data.md` : the Publications Office as infrastructure operator
- `eurovoc_thesaurus.md` : EuroVoc thematic vocabulary used for dataset classification
- `cellar_semantic_repository.md` (planned) : Cellar, the semantic repository underlying EU legal documents
- `eu_high_value_datasets_hvd_reg_2023_138.md` (planned) : HVD implementing regulation and obligations
- `eu_legal_data_space_elds.md` (planned) : ELDS sub-portal for legal data
- `eu_procurement_data_space_ppds_eforms.md` (planned) : PPDS sub-portal for procurement data
- `cordis_research_projects_database.md` (planned) : CORDIS open research data from Horizon Europe
