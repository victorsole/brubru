# Specialised EC Databases — v1 Endpoint Roadmap

**Status:** Discovery complete, ship in waves. Created 8 May 2026.
**Goal:** publish a "Specialised EC Databases" Postman collection mirroring every reasonably accessible Commission-managed registry/database/portal — same shape as the rest of the v1 surface (5-section Markdown description, `body_html`/`body_text`/`has_body` fields, `body_threshold` query, plain-English item names).

Total surveyed: **~66 databases** across 13 thematic clusters. Realistic v1 target: **30–40 endpoints** (the 🟢 + most 🟡 + a curated set of 🔴).

Access mode legend:
- 🟢 — JSON/REST or OGC API
- 🟡 — structured download / RSS / bulk XML or CSV
- 🔴 — HTML scrape only (parser required)
- ⚫ — closed / authenticated / restricted; defer indefinitely

---

## Sequencing (locked 8 May 2026)

| Wave | Cluster | Why first |
|------|---------|-----------|
| 1 | **Trade & Customs** | Aligned with DG TRADE / GovClipping partnership / existing v1 surface. |
| 2 | **Chemicals (ECHA)** | High-traffic regulatory queries; ECHA has real export APIs. |
| 3 | **Food, Feed & Plant Health** | eAmbrosia is unique to EU; RASFF Window has high journalistic value. |
| 4 | **Competition + State Aid** | Politically interesting, well-defined endpoints. |
| 5 | **Knowledge Centres / JRC** | Ready data portals (CKAN, OGC). |
| 6 | **Marine & Environment** | EMODnet / WISE / BISE / Copernicus — bulk OGC. |
| 7 | **Economy & Finance (DG ECFIN)** | AMECO, Fiscal Gov, EU KLEMS — bulk Excel / CSV ingestion. |
| 8 | **Transparency & Decision-Making** | Transparency Register, Comitology, Expert Groups. |
| 9 | **Energy / Education / Regional** | Tail; ENTSO-E + ESCO + Cohesion. |
| - | Justice / Migration / Home Affairs | Closed → defer. |

Each wave proceeds in this order: scraper → migration → SQLAlchemy model → Pydantic schema with body fields → FastAPI router with 5-section description → backfill script → Postman push.

---

## 1. Chemicals & Substances (ECHA)

| # | Database | URL | Access |
|---|----------|-----|--------|
| 1.1 | REACH Registered Substances | https://chem.echa.europa.eu/registered-substances | 🟡 |
| 1.2 | CLP Inventory | https://chem.echa.europa.eu/cl-inventory | 🟡 |
| 1.3 | Biocidal Products Register | https://chem.echa.europa.eu/biocidal-products | 🟡 |
| 1.4 | SCIP database (substances of concern in articles) | https://echa.europa.eu/scip-database | 🟡 |
| 1.5 | Candidate List / SVHC | https://echa.europa.eu/candidate-list-table | 🟡 |
| 1.6 | Annex XVII REACH (restricted substances) | https://echa.europa.eu/substances-restricted-under-reach | 🔴 |
| 1.7 | PIC (Prior Informed Consent — hazardous chemicals export) | https://echa.europa.eu/information-on-chemicals/pic | 🔴 |

## 2. Food, Feed & Plant Health (DG SANTE)

| # | Database | URL | Access |
|---|----------|-----|--------|
| 2.1 | eAmbrosia (Geographical Indications) | https://ec.europa.eu/agriculture/eambrosia/geographical-indications-register/ | 🟡 |
| 2.2 | RASFF Window (food/feed alerts) | https://webgate.ec.europa.eu/rasff-window | 🔴 |
| 2.3 | iRASFF (admin layer) | https://webgate.ec.europa.eu/irasff | ⚫ |
| 2.4 | TRACES NT (sanitary/phytosanitary certificates) | https://webgate.ec.europa.eu/tracesnt | 🔴/⚫ |
| 2.5 | EUROPHYT (plant-health interceptions) | https://webgate.ec.europa.eu/europhyt | 🔴 |
| 2.6 | ADIS (animal disease notifications) | https://webgate.ec.europa.eu/tracesnt/adis/public | 🔴 |
| 2.7 | EU Pesticides Database | https://ec.europa.eu/food/plant/pesticides/eu-pesticides-database | 🟡 |
| 2.8 | EU Plant Variety Portal | https://ec.europa.eu/plant-variety-portal | 🔴 |
| 2.9 | FOREMATIS | https://ec.europa.eu/forematis | 🔴 |
| 2.10 | Food & Feed Information Portal — 13 sub-screens (additives, allergens, FCM, flavourings, GMOs, health claims, IFFOF, novel food, nutrients, smoke flavourings, decontamination) | https://ec.europa.eu/food/food-feed-portal | 🔴 |
| 2.11 | DG SANTE Audit & Analysis | https://ec.europa.eu/food/audits-analysis | 🔴 |

## 3. Trade & Customs *(WAVE 1)*

| # | Database | URL | Access |
|---|----------|-----|--------|
| 3.1 | TARIC (integrated tariff) | https://ec.europa.eu/taxation_customs/dds2/taric | 🟡 (XML bulk) |
| 3.2 | CBAM register | TARIC integrated since 2026-01-01 | 🟡 |
| 3.3 | Access2Markets / ROSA | https://trade.ec.europa.eu/access-to-markets | 🔴 |
| 3.4 | Single Entry Point (trade barriers) | https://trade.ec.europa.eu/access-to-markets/en/barriers | 🔴 |
| 3.5 | Trade Defence cases (anti-dumping, anti-subsidy, safeguard) | https://tron.trade.ec.europa.eu/investigations | 🔴 |
| 3.6 | DG TAXUD Surveillance | DG TAXUD | ⚫ (auth) |
| 3.7 | Treaties Office Database (Council bilateral & multilateral agreements) | https://www.consilium.europa.eu/en/documents/treaties-agreements | 🔴 |
| 3.8 | CIRCABC (collaborative documents) | https://circabc.europa.eu | 🟡 (REST) |

## 4. Health & Medical Devices

| # | Database | URL | Access |
|---|----------|-----|--------|
| 4.1 | EUDAMED (medical devices, IVD) | https://webgate.ec.europa.eu/eudamed | 🔴 |
| 4.2 | COSING (cosmetic ingredients) | https://ec.europa.eu/growth/tools-databases/cosing | 🔴 |
| 4.3 | EU-CEG (tobacco common entry gate) | https://ec.europa.eu/health/euceg | ⚫ |
| 4.4 | EU Vaccines Portal | https://health.ec.europa.eu/vaccination/eu-vaccines-strategy_en | 🔴 |
| 4.5 | SoHO registries (Substances of Human Origin) | DG SANTE | 🔴 |

## 5. Economy & Finance (DG ECFIN)

| # | Database | URL | Access |
|---|----------|-----|--------|
| 5.1 | AMECO | https://ec.europa.eu/economy_finance/ameco | 🟡 |
| 5.2 | Fiscal Governance Database | DG ECFIN | 🟡 |
| 5.3 | CeSaR (Country-Specific Recommendations) | https://ec.europa.eu/economy_finance/country-specific-recommendations-database | 🔴 |
| 5.4 | Key Indicators for the Euro Area | DG ECFIN | 🟡 |
| 5.5 | Price & Cost Competitiveness | DG ECFIN | 🟡 |
| 5.6 | Stability & Convergence Programmes | DG ECFIN | 🟡 |
| 5.7 | EU KLEMS | https://euklems.eu | 🟡 |
| 5.8 | Tax & Benefits Indicators | DG ECFIN | 🟡 |

## 6. Research, Innovation, Knowledge (JRC + R&I)

| # | Database | URL | Access |
|---|----------|-----|--------|
| 6.1 | CORDIS *(already in v1)* | https://cordis.europa.eu | 🟢 |
| 6.2 | JRC Data Catalogue | https://data.jrc.ec.europa.eu | 🟢 (CKAN) |
| 6.3 | Knowledge4Policy — 8 Knowledge Centres (Bioeconomy / Disaster Risk / Food Fraud & Quality / Global Food & Nutrition Security / Migration & Demography / Territorial / Cancer / Biodiversity) | https://knowledge4policy.ec.europa.eu | 🔴 |
| 6.4 | DataM | https://datam.jrc.ec.europa.eu | 🟡 |
| 6.5 | ESDAC (European Soil Data Centre) | https://esdac.jrc.ec.europa.eu | 🟡 |
| 6.6 | EFFIS (forest fire info system) | https://forest-fire.emergency.copernicus.eu | 🟢 (WMS/WFS) |
| 6.7 | LUISA | https://publications.jrc.ec.europa.eu | 🟡 |
| 6.8 | INSPIRE Geoportal | https://inspire-geoportal.ec.europa.eu | 🟢 |
| 6.9 | EOSC | https://open-science-cloud.ec.europa.eu | 🟢 |

## 7. Marine & Environment

| # | Database | URL | Access |
|---|----------|-----|--------|
| 7.1 | EMODnet (7 thematic portals) | https://emodnet.ec.europa.eu | 🟢 |
| 7.2 | WISE | https://water.europa.eu | 🟢 |
| 7.3 | BISE | https://biodiversity.europa.eu | 🟢 |
| 7.4 | EEA datasets | https://eea.europa.eu/data-and-maps | 🟢 |
| 7.5 | Copernicus services (CAMS/CLMS/CMEMS/C3S/EMS/CSS) | https://copernicus.eu | 🟢 |

## 8. Transparency & Decision-Making

| # | Database | URL | Access |
|---|----------|-----|--------|
| 8.1 | Transparency Register | https://transparency-register.europa.eu | 🟡 |
| 8.2 | Comitology Register | https://ec.europa.eu/transparency/comitology-register | 🟡 |
| 8.3 | Expert Group Register | https://commission.europa.eu/about/service-standards-and-principles/transparency/register-expert-groups | 🔴 |
| 8.4 | RegDoc (Register of Commission Documents) | https://ec.europa.eu/transparency/documents-register | 🔴 |
| 8.5 | Commissioners' Meetings register | DG SG | 🔴 |

## 9. State Aid & Competition (DG COMP)

| # | Database | URL | Access |
|---|----------|-----|--------|
| 9.1 | Competition Cases (mergers + antitrust + state aid) | https://competition-cases.ec.europa.eu | 🔴 |
| 9.2 | State Aid Register | https://ec.europa.eu/competition/state_aid/register | 🔴 |
| 9.3 | TAM (Transparency Award Module) | https://webgate.ec.europa.eu/competition/transparency | 🔴 |
| 9.4 | eLeniency | DG COMP | ⚫ |

## 10. Energy

| # | Database | URL | Access |
|---|----------|-----|--------|
| 10.1 | ENTSO-E Transparency Platform | https://transparency.entsoe.eu | 🟢 |
| 10.2 | ENTSOG Transparency Platform | https://transparency.entsog.eu | 🟢 |
| 10.3 | National Energy & Climate Plans tracker | https://commission.europa.eu | 🔴 |
| 10.4 | EU Energy Statistical Pocketbook | DG ENER | 🟡 |

## 11. Education & Skills

| # | Database | URL | Access |
|---|----------|-----|--------|
| 11.1 | ESCO | https://esco.ec.europa.eu | 🟢 |
| 11.2 | Eurydice | https://eurydice.eacea.ec.europa.eu | 🔴 |
| 11.3 | EQAVET | EACEA | 🔴 |

## 12. Justice, Migration, Home Affairs *(mostly closed — DEFER)*

| # | Database | URL | Access |
|---|----------|-----|--------|
| 12.1 | e-Justice Portal | https://e-justice.europa.eu | 🔴 |
| 12.2 | VIS / SIS II / Eurodac / ECRIS-TCN | DG HOME | ⚫ |

## 13. Regional Policy & Cohesion

| # | Database | URL | Access |
|---|----------|-----|--------|
| 13.1 | Cohesion Open Data Platform | https://cohesiondata.ec.europa.eu | 🟢 |
| 13.2 | Inforegio Data | https://ec.europa.eu/regional_policy | 🔴 |

---

## Per-endpoint contract (must match existing v1 surface)

1. **Plain-English name** — no CELEX/CORDIS/etc. jargon as the primary name.
2. **5-section Markdown description**: What it does / When to use it / Input / Try it / You get back.
3. **Body fields** — every detail row exposes `has_body`, `body_html` (HTML when source is HTML; null for PDF-sourced), `body_text` (always non-null when `has_body=true`).
4. **`body_threshold`** query parameter (default 500, range [0, 100000]) on every list and detail endpoint.
5. **No nulls in primary metadata** — backfill script must populate every column the schema declares non-null. If the upstream source genuinely has no value, the schema field must be `Optional` and the JSON omits it (not `null`).
6. **Postman collection sub-folder** named exactly as the cluster header in this file.
7. **Postman item description** mirrors the OpenAPI Markdown description verbatim (synced via `/postman` skill).

---

## Working file locations

- This roadmap: `docs/applications/specialised_ec_databases.md`
- Memory pointer: `memory/project_specialised_ec_databases.md`
- API routers: `backend/api/v1/<topic>.py` (one file per database OR per cluster, decided per-wave)
- Migrations: `backend/alembic/versions/<NNN>_specialised_ec_<topic>.py`
- Models: `backend/models/specialised/*.py`
- Scrapers: `backend/services/scrapers/specialised/*.py`
- Backfill: `backend/scripts/backfill_<topic>.py`

---

## Progress tracker

| Wave | Status | Endpoints shipped | Postman pushed | Date |
|------|--------|-------------------|----------------|------|
| 1 — Trade & Customs | in progress | 2 / ~18 (Treaties via Cellar SPARQL — list + detail) | yes | 2026-05-08 |
| 2 — Chemicals | not started | 0 / ~14 | – | – |
| 3 — Food/Feed/Plant | not started | 0 / ~15 | – | – |
| 4 — Competition | not started | 0 / ~6 | – | – |
| 5 — JRC / Knowledge | not started | 0 / ~12 | – | – |
| 6 — Marine/Env | not started | 0 / ~8 | – | – |
| 7 — Economy/Finance | not started | 0 / ~8 | – | – |
| 8 — Transparency | not started | 0 / ~5 | – | – |
| 9 — Energy/Education/Regional | not started | 0 / ~6 | – | – |

Update this table after each wave; commit alongside the code.
