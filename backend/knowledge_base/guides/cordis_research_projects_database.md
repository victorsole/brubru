# CORDIS: the EU Research Projects Database

## QUICK FACTS
- **What it is**: Community Research and Development Information Service (CORDIS), the official EU portal for results of EU-funded research and innovation projects
- **Run by**: Publications Office of the European Union (an interinstitutional body serving all EU institutions; not a Commission DG); see `eu_publications_office_and_open_data.md`
- **Coverage**: every EU framework programme from FP1 (1984) to Horizon Europe (2021-2027), plus CIP, COSME, LIFE, ERC, MSCA, Eurostars, EIT, EUREKA, JTI, JU, FET, and EURATOM
- **Scale**: approximately 1.3 million projects; millions of associated deliverables, publications, results, and news items
- **Primary URL**: https://cordis.europa.eu/
- **Projects search**: https://cordis.europa.eu/projects
- **Data laboratory**: https://cordis.europa.eu/datalab (SPARQL endpoint on the EURIO knowledge graph, REST API, visualisations, widget builder, Data Extraction Tool)
- **Open data dumps**: CSV, JSON, and RDF bulk exports on data.europa.eu; the Horizon Europe 2021-2027 pack is at https://data.europa.eu/data/datasets/cordis-eu-research-projects-under-horizon-europe-2021-2027; 11 thematic packs in total, covering every programme
- **Key entities exposed per project**: acronym, title, start/end dates, total cost, EU funded amount, call and topic reference, funding scheme, programme; per beneficiary: organisation name, type, country, and net EU contribution; plus deliverables, publications, results, and news items
- **Relationship to F&T Portal**: CORDIS covers outputs (what funded projects produced); the Funding and Tenders Portal covers inputs (open calls, submitted proposals, grant agreements and contracts); the two services are complementary, not overlapping; see `eu_funding_ft_portal_online_manual.md`
- **Linked data layer**: the EURIO (EU Research Information Ontology) knowledge graph in CORDIS DataLab exposes all project data as Linked Open Data, queryable via a public SPARQL endpoint
- **Language**: multilingual; all official EU languages; open licence; all data freely reusable

How to find, understand, and extract data on every EU-funded research project ever registered in the CORDIS system.

## What CORDIS Is

CORDIS (Community Research and Development Information Service) is the Publications Office's public-facing portal and structured data service for EU-funded research and innovation. It was established in the early 1990s to disseminate results from the Framework Programmes and has since grown into a comprehensive repository covering every programme from FP1 (1984) through to the current Horizon Europe (2021-2027).

Unlike the Funding and Tenders Portal, which manages the application and contracting pipeline, CORDIS focuses on the downstream side: which projects were selected, who carried them out, how much each beneficiary received, and what they produced. It is the canonical public record of EU research investment and the primary data source for any question about where EU research money went and what it achieved.

CORDIS is openly licensed and freely reusable. The Publications Office publishes quarterly bulk-download packs for programmatic reuse, and the CORDIS DataLab provides a SPARQL endpoint, a REST API, and several interactive visualisation tools.

## Coverage Across Framework Programmes

CORDIS holds project records for every programme that uses the common EU project registration system. Coverage by programme is as follows.

### Framework Programmes (research and technological development)

- **FP1** (1984-1987): first Framework Programme for RTD
- **FP2** (1987-1991): second Framework Programme
- **FP3** (1990-1994): third Framework Programme
- **FP4** (1994-1998): fourth Framework Programme
- **FP5** (1998-2002): fifth Framework Programme; Quality of Life, User-friendly Information Society, Competitive and Sustainable Growth, Energy, Environment and Sustainable Development, Confirming the International Role of Community Research
- **FP6** (2002-2006): sixth Framework Programme; NEST, New and Emerging Science and Technology included
- **FP7** (2007-2013): seventh Framework Programme; seven specific programmes: Ideas (ERC), People (MSCA precursor), Capacities, Cooperation, Euratom, JRC, Security; approximately 25,000 projects
- **Horizon 2020** (2014-2020): approximately 40,000 projects; three pillars (Excellent Science, Industrial Leadership, Societal Challenges) plus ERC, MSCA, FET, Euratom and the SME Instrument
- **Horizon Europe** (2021-2027): the current programme; five components: Excellent Science (ERC, MSCA, research infrastructures), Global Challenges and European Industrial Competitiveness (six clusters), Innovative Europe (EIC, EIT, EIPs), Widening Participation and Strengthening the ERA, and Reform and Enhancement of the European R&I System

### Thematic and Complementary Programmes

- **ERC** (European Research Council): frontier research grants; Starting, Consolidator, Advanced, Synergy, and Proof of Concept grant types
- **MSCA** (Marie Sklodowska-Curie Actions): researcher mobility and training; ITN/DN, COFUND, RISE, IF/PF, SE schemes; see `marie_sklodowska_curie_actions.md` (planned)
- **EIT** (European Institute of Innovation and Technology): eight Knowledge and Innovation Communities (EIT Digital, EIT Health, EIT InnoEnergy, EIT Climate-KIC, EIT Manufacturing, EIT Food, EIT Urban Mobility, EIT RawMaterials)
- **EIC** (European Innovation Council): Pathfinder, Transition, Accelerator; see `eic_overview.md`
- **JTI/JU** (Joint Technology Initiatives and Joint Undertakings): Clean Hydrogen JU, Europe's Rail JU, SESAR 3 JU, KDT JU, Innovative Health Initiative JU, Global Health EDCTP3 JU, Smart Networks and Services JU, Chips JU, Circular Bio-based Europe JU, BeOpen JU, and predecessors
- **FET** (Future and Emerging Technologies, now Pathfinder): high-risk/high-gain exploratory research
- **EUREKA**: intergovernmental network for market-oriented R&D; CORDIS holds the Eurostars subset (R&D-performing SMEs)
- **Eurostars**: dedicated SME programme operating under EUREKA and co-funded by Horizon Europe
- **CIP** (Competitiveness and Innovation Framework Programme, 2007-2013): ICT Policy Support Programme, Intelligent Energy Europe, Entrepreneurship and Innovation Programme
- **COSME** (Competitiveness of Enterprises and SMEs, 2014-2020): now integrated into the Single Market Programme
- **LIFE**: environment and climate action programme; Nature and Biodiversity, Circular Economy and Quality of Life, Clean Energy Transition, Climate Change Adaptation, and Mitigation sub-programmes; see `eu_commission_funding_programmes_map.md`
- **EURATOM**: nuclear research programme under the Euratom Treaty; runs in parallel with the Framework Programmes

## The Data Model

CORDIS organises information around a hierarchy of **project**, **beneficiary**, and downstream **outputs**.

### Project record

Each project record exposes: a unique CORDIS project number; the acronym and full title; the funding call identifier and topic reference; the programme, sub-programme, and funding scheme (Research and Innovation Action, Innovation Action, Coordination and Support Action, MSCA Doctoral Networks, etc.); start and end dates; the total project cost; the EU funded amount (the grant ceiling); a plain-language objective and summary; status (SIGNED, TERMINATED, CLOSED); and links to all associated beneficiaries, deliverables, publications, results, and news.

### Beneficiary records

Each project links to one or more beneficiary organisations. For each beneficiary, CORDIS records: the organisation's legal name; the Organisation ID (an internal OP identifier); the organisation type (higher or secondary education, research organisation, private for-profit, private non-profit, public body, other); the country; and the net EU contribution received by that organisation under the project. For consortium projects, the coordinating organisation is flagged.

### Downstream outputs

- **Deliverables**: contractual reports, datasets, data management plans, and other outputs uploaded to the Commission's research information system (SYGMA/PPGMS) and made public; available for Horizon Europe and Horizon 2020 projects
- **Publications**: peer-reviewed papers, conference papers, and other publications produced under the project, linked via OpenAIRE (the EU open-access research infrastructure); each publication carries a DOI where available
- **Results** (formerly "technology results"): commercial or deployable outputs voluntarily registered by the project team; prototypes, datasets, software, methods, spin-offs
- **News**: project-submitted press releases and news items
- **Reports**: periodic and final reports, where made public by the project team

## How to Access CORDIS Data

### Web search

The main project search at https://cordis.europa.eu/projects supports free-text queries combined with filters for programme, country, organisation type, keyword, call/topic identifier, project status, funding scheme, start year, and end year. Results can be sorted by relevance or start date. A CSV export of the current result set is available directly from the search results page without registration.

### Open data bulk downloads

The Publications Office publishes regular CSV, JSON, and RDF bulk exports on data.europa.eu. These are the preferred vehicle for large-scale analysis. The 11 thematic packs are:

| Pack | Programmes covered |
|---|---|
| Horizon Europe 2021-2027 | HE ERC, MSCA, all six clusters, EIC, Widening, Missions, Euratom |
| Horizon 2020 | H2020 all pillars |
| FP7 | Seventh Framework Programme |
| FP6 | Sixth Framework Programme |
| FP5 | Fifth Framework Programme |
| FP4 | Fourth Framework Programme |
| FP3 | Third Framework Programme |
| FP2 | Second Framework Programme |
| FP1 | First Framework Programme |
| EURATOM | Nuclear research programme (all periods) |
| Other programmes | CIP, COSME, LIFE, Eurostars, EUREKA, EIT |

Each pack contains a projects file and an organisations file keyed on the CORDIS project number. The Horizon Europe and Horizon 2020 packs additionally include deliverables, publications, and results files. All files are in CSV and JSON; the Horizon Europe pack is also available in RDF (EURIO-compliant Turtle). For programmatic pipelines, the data.europa.eu dataset pages expose stable dataset identifiers and DCAT-AP metadata, making them preferable to direct CORDIS download links.

Dataset landing page (Horizon Europe 2021-2027 pack): https://data.europa.eu/data/datasets/cordis-eu-research-projects-under-horizon-europe-2021-2027

### CORDIS REST API (registered users)

Via the CORDIS DataLab, registered users can query the underlying EURIO knowledge graph programmatically. The REST API returns JSON-LD. Registration is free and open to all. The API is documented at the DataLab.

### SPARQL (EURIO knowledge graph)

The SPARQL endpoint at the DataLab allows complex joined queries across projects, organisations, deliverables, publications, and results in a single query. EURIO (EU Research Information Ontology) is a W3C-compliant Linked Data ontology; each entity is resolvable as a persistent URI.

### Data Extraction Tool (DET)

Available from within any CORDIS search result page, the DET allows registered users to download the current result set in structured format. It supports larger result sets than the unauthenticated CSV export.

## Thematic Packs

The 11 thematic packs (see the table above) are updated quarterly for active programmes (Horizon Europe) and annually or on-demand for closed programmes. Each pack download page on data.europa.eu lists the exact revision date and a data dictionary.

For analysis tasks that span multiple programmes (for example, tracing an organisation's total EU research funding from FP5 through to Horizon Europe), the correct approach is to download the relevant packs, join on the `organisationID` or the legal name + country combination (note that `organisationID` is stable within a pack but not guaranteed stable across different pack vintages; use legal name + country as the durable join key), and sum the `ecContribution` field across all rows.

## CORDIS DataLab

The CORDIS DataLab at https://cordis.europa.eu/datalab provides five main services.

**EURIO SPARQL endpoint**: the complete CORDIS database exposed as Linked Open Data, queryable via SPARQL 1.1. EURIO follows the W3C RDF Data Cube Vocabulary for statistical data and the SKOS vocabulary for thematic tagging. Queries can join projects, organisations, publications, and deliverables in a single call.

**Collaboration Network**: an interactive graph visualisation of co-participation between organisations across Horizon Europe. Useful for identifying consortium patterns, repeated partnerships, and cross-border collaboration networks relevant to a given topic.

**Project Map**: a geographic visualisation of project participation by country and NUTS region, filterable by programme, topic, and year range.

**Widget Wizard**: allows any external organisation (university, agency, national contact point) to embed a live, auto-refreshing CORDIS search panel into their own website, filtered to their area.

**Data Extraction Tool**: exports any live CORDIS search result set in structured format; available to registered users.

## How Brubru Uses CORDIS

### Financial trail ("EU money received")

CORDIS is the primary data source for any query about which organisations received EU research funding and how much. The `organisation.csv` file in each programme pack, with its `ecContribution` field (net EU contribution per beneficiary per project), is the spine of the financial trail. Queries of the type "has [organisation] received Horizon 2020 funding?", "what was [university]'s total FP7 income?", or "which Belgian SMEs have EIC Accelerator grants?" all resolve directly from these files. This connects to the `data/financial_data.md` strategy for the "EU money received" product surface.

### Tenderator context

For calls under Horizon Europe and related programmes, CORDIS records of previous awards under the same topic or call are useful competitive intelligence before submitting a proposal. Combined with call information from the Funding and Tenders Portal (see `eu_funding_ft_portal_online_manual.md`), they show the typical consortium composition, average grant size, and success rate for a given topic.

### Chat knowledge base

CORDIS enriches answers to questions such as: "Has [organisation] received EU research funding?"; "What research projects are running on [topic]?"; "Which organisations are leading Horizon Europe work on [subject]?"; "What did FP7 project [name] produce?"; "How much did [country] receive from Horizon 2020?".

### Future: CORDIS as a data API endpoint

The EURIO SPARQL endpoint and the REST API are candidates for a dedicated Brubru API v2 endpoint surfacing project and beneficiary data. The data.europa.eu SPARQL endpoint also exposes CORDIS dataset metadata. Both are documented in `docs/api/`.

## Comparison with the Funding and Tenders Portal

| Aspect | CORDIS | Funding and Tenders Portal |
|---|---|---|
| Focus | Funded projects and their outputs | Open calls, proposals, grant agreements |
| Typical user | Researcher, analyst, journalist, policy officer | Grant applicant, project manager, beneficiary |
| What it tracks | Awarded projects and results | Live calls, submitted proposals, contracts |
| Beneficiary financials | Yes, net EU contribution per organisation | Yes, grant agreement amounts |
| Access model | Fully open; bulk download; public SPARQL | Registered participants; eSingle API |
| Data freshness | Quarterly bulk refresh; near-real-time search for active projects | Near-real-time for call deadlines |
| Guide | This guide | `eu_funding_ft_portal_online_manual.md` |

The two services complement each other: the F&T Portal for the prospective (applying, managing a project, checking call deadlines), CORDIS for the retrospective (what was funded, who benefited, what was produced).

## Cross-References

- `eu_commission_funding_programmes_map.md`: the full map of EU funding programmes under which CORDIS projects sit
- `eu_publications_office_and_open_data.md`: the Publications Office's broader role (CORDIS, EUR-Lex, TED, data.europa.eu, EU Vocabularies)
- `horizon_europe_grant_management.md`: Horizon Europe grant management, the Annotated Grant Agreement, and the AGA
- `eu_funding_ft_portal_online_manual.md`: the Funding and Tenders Portal (the application and contracting side)
- `eic_overview.md`: European Innovation Council; EIC projects also appear in CORDIS under the Horizon Europe pack
- `marie_sklodowska_curie_actions.md` (planned): MSCA fellowships and doctoral networks; MSCA projects are fully covered in CORDIS
- `data_europa_eu_open_data_portal.md` (planned): the full data.europa.eu open-data portal covering all EU institutions, including the CORDIS bulk download packs
