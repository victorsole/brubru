# Eurostat Statistics Production

## QUICK FACTS
- Topic: European Statistical System, data collection methodologies, quality frameworks, international trade in services statistics
- Scope: EU statistics production and dissemination
- Responsible institution: Eurostat (statistical office of the EU), coordinating with 27 National Statistical Institutes
- Framework regulation: European Business Statistics Regulation (EU) 2019/2152 (replaced 10 previous regulations)
- Confidentiality regulation: Regulation (EC) 223/2009
- Code of Practice: 16 principles in 3 areas (institutional environment, statistical processes, statistical output)
- ITSS classification: EBOPS 2010 (12 service categories: SA-SL)
- Quality dimensions: Relevance, accuracy, timeliness, punctuality, comparability, coherence, accessibility
- Peer reviews: Every 5 years per NSI (self-assessment + independent expert visit)
- Validation stages: Pre-validation, plausibility checks, anomaly detection, bilateral queries, revision analysis, publication clearance
- Embargo: Publications embargoed until official release time (typically 11:00 CET)
- **Eurostat data release (22 April 2026): "Drought hits 156,703 km² of EU land in 2024"** -- Eurostat + Copernicus soil moisture data release. Affected area equivalent to almost 4% of EU land mass. Southern + Mediterranean Member States (Spain, Italy, Portugal, Greece) + South-Eastern (Romania, Bulgaria) worst affected. Feeds directly into CAP 2023-2027 climate adaptation debate + post-2027 natural-disasters MFF funding (BUDG_ATA(2026)785762). Link: ec.europa.eu/eurostat product ddn-20260422-1.
- **Eurostat data release (22 April 2026): "Government finance statistics: updated information"** -- quarterly GFS update feeding EDP / SGP compliance assessment.
- **Eurostat data release (23 April 2026): "Digitalisation in Europe -- new edition out today"** -- Annual flagship "Digital Economy and Society" statistics publication. Covers digital infrastructure, connectivity, business digitalisation, e-commerce, e-government, digital skills. Feeds Digital Decade 2030 targets monitoring.
- **Eurostat data release (23 April 2026): "EU aquaculture: 1 million tonnes produced in 2024"** -- EU aquaculture annual production data. 1M tonnes milestone. Top producers by volume: Spain (mussels + sea bream), France (oysters), Greece (sea bream + sea bass), Italy, Ireland (salmon), Denmark (trout). Feeds Farm to Fork + animal welfare debate (see `farmed_fish_welfare_eu`, DG SANTE gaps report 23 April).
- **Eurostat data release (23 April 2026): "EU girls excel in digital skills, but trail in coding"** -- Gender-disaggregated digital skills data. Girls match or exceed boys in general digital skills but underrepresented in coding/programming. Feeds EU Digital Education Action Plan + Women in Digital initiative + STEM pipeline discussions.
- **Eurostat data release (23 April 2026): "More people bought e-books and audio books in 2025"** -- Household consumption survey showing rising share of digital publications purchases. Relevant for VAT policy on e-books (parity with print since Directive (EU) 2018/1713), cultural industry monitoring, Creative Europe programme.

Guide for Eurostat statisticians and data analysts covering the European Statistical System, data collection methodologies, quality frameworks, and international trade in services statistics.

## European Statistical System (ESS)

### Structure

| Entity | Role |
|--------|------|
| **Eurostat** | Statistical office of the EU; coordinates the ESS |
| **National Statistical Institutes (NSIs)** | Primary data producers in each Member State (e.g. INSEE, Destatis, ISTAT, INE) |
| **Other National Authorities (ONAs)** | Sector-specific statistics producers (central banks, ministries) |
| **ESSC (European Statistical System Committee)** | Governance body; adopts work programme, discusses strategic and methodological issues |

### European Statistics Code of Practice

16 principles organised in three areas:

| Area | Principles |
|------|-----------|
| **Institutional environment** | Professional independence (P1), Coordination and cooperation (P1bis), Mandate for data collection (P2), Adequacy of resources (P3), Commitment to quality (P4), Statistical confidentiality (P5), Impartiality and objectivity (P6) |
| **Statistical processes** | Sound methodology (P7), Appropriate statistical procedures (P8), Non-excessive burden on respondents (P9), Cost effectiveness (P10) |
| **Statistical output** | Relevance (P11), Accuracy and reliability (P12), Timeliness and punctuality (P13), Coherence and comparability (P14), Accessibility and clarity (P15), Metadata management (P16) |

### Peer Reviews

ESS conducts peer reviews of each NSI approximately every 5 years:
1. Self-assessment questionnaire
2. Peer review team (independent experts) visits NSI
3. Published peer review report with improvement actions
4. Follow-up monitoring

## European Business Statistics Regulation (EU) 2019/2152

### Scope

Replaced 10 previous regulations with a single framework covering:
- Business demographics (births, deaths, survival)
- Short-term business statistics (production, turnover, orders)
- Structural business statistics (value added, employment, investment)
- International trade in services (ITSS)
- Foreign affiliates statistics (FATS)
- Foreign direct investment (FDI)
- R&D and innovation statistics

### Data Collection

| Method | Description | Used For |
|--------|-------------|----------|
| **Surveys** | Questionnaires to enterprises (paper/electronic) | SBS, ITSS, R&D |
| **Administrative data** | Tax records, social security, business registers | Business demographics, short-term |
| **Statistical registers** | EuroGroups Register (EGR), national business registers | FATS, FDI, multinational profiling |
| **Big data/web scraping** | Experimental (job vacancies, prices) | Supplementary, not primary source |

## International Trade in Services Statistics (ITSS)

### Classification: EBOPS 2010

Extended Balance of Payments Services Classification:

| Code | Category | Examples |
|------|----------|---------|
| SA | Manufacturing services on physical inputs | Contract manufacturing, assembly |
| SB | Maintenance and repair | Aircraft, ship repair |
| SC | Transport | Freight, passenger, postal |
| SD | Travel | Business, personal, education, health |
| SE | Construction | Abroad, in compiling economy |
| SF | Insurance and pension services | Direct insurance, reinsurance |
| SG | Financial services | Banking, securities, derivatives |
| SH | Charges for IP use | Licences, franchises, trademarks |
| SI | Telecommunications, computer, information | IT services, data processing |
| SJ | Other business services | R&D, consulting, management, trade-related |
| SK | Personal, cultural, recreational | Audio-visual, education, health |
| SL | Government goods and services | Embassies, military, international organisations |

### Modes of Supply (GATS Framework)

| Mode | Description | Statistical Measurement |
|------|-------------|------------------------|
| **Mode 1** | Cross-border supply | Balance of payments (ITSS) |
| **Mode 2** | Consumption abroad | Travel statistics (partly) |
| **Mode 3** | Commercial presence | Foreign Affiliates Statistics (FATS) |
| **Mode 4** | Presence of natural persons | Labour statistics, migration data |

### Data Compilation

#### Sources

| Source | Data | Coverage |
|--------|------|----------|
| **Balance of payments** | Central bank BoP data (BPM6 methodology) | Aggregate, all services |
| **Enterprise surveys** | Direct surveys to services exporters/importers | Detailed EBOPS breakdown |
| **ITRS (International Transaction Reporting System)** | Bank settlement records | Declining use (many countries phased out) |
| **Administrative data** | VAT (MOSS), social security, immigration | Supplementary |

#### Challenges

| Challenge | Description | Mitigation |
|-----------|-------------|-----------|
| **Asymmetries** | Country A reports EUR 100M exports to B; B reports EUR 80M imports from A | Bilateral reconciliation exercises |
| **STEC linkage** | Linking services trade to enterprise characteristics (size, sector, ownership) | Statistical matching via business registers |
| **Globalisation effects** | Transfer pricing, SPEs, merchanting distort statistics | National accounts' treatment, SPE filtering |
| **Digital services** | Cross-border digital services hard to capture (cloud, SaaS) | New survey questions, web scraping experiments |
| **Confidentiality** | Individual enterprise data cannot be disclosed | Aggregation, cell suppression, rounding |

## Data Validation and Quality

### Validation Process

| Stage | Description |
|-------|-------------|
| **Pre-validation** | Automated checks on data format, completeness, consistency |
| **Plausibility checks** | Year-on-year changes, cross-country comparison, time series analysis |
| **Anomaly detection** | Statistical flags for values outside expected ranges |
| **Bilateral queries** | Formal queries to NSIs requesting clarification (see `data_quality_query_template.md`) |
| **Revision analysis** | Track magnitude and direction of data revisions |
| **Publication clearance** | Final review before dissemination |

### Quality Reports

Each statistical domain produces quality reports covering:

| Dimension | Description | Typical Indicators |
|-----------|-------------|-------------------|
| **Relevance** | Meeting user needs | User satisfaction surveys, consultation results |
| **Accuracy** | Proximity to true value | Sampling error (CV), non-sampling error, revision magnitude |
| **Timeliness** | Time between reference period and publication | Publication calendar compliance |
| **Punctuality** | Adherence to planned release date | Percentage of on-time releases |
| **Comparability** | Cross-country and over-time consistency | Breaks in series, methodology changes |
| **Coherence** | Consistency with other statistics and national accounts | Reconciliation with BoP, national accounts |
| **Accessibility** | Ease of data access | Eurostat database, metadata, documentation |

### Asymmetry Analysis

For bilateral trade in services:

1. **Identify asymmetries**: Compare mirror statistics (A's exports to B vs B's imports from A)
2. **Quantify**: Calculate absolute and percentage differences
3. **Classify causes**: Methodological, coverage, timing, classification, or genuine error
4. **Reconciliation exercises**: Bilateral meetings between NSIs to align methodologies
5. **Adjustment**: If warranted, agreed adjustments reflected in next data transmission

## Confidentiality Management

### Legal Basis

- **Regulation (EC) 223/2009**: Statistical confidentiality rules for EU statistics
- **European Statistics Code of Practice, Principle 5**: Statistical confidentiality

### Methods

| Method | Description |
|--------|-------------|
| **Cell suppression** | Suppress cells where individual enterprises could be identified |
| **Primary suppression** | Suppress cell if fewer than 3 enterprises or one dominates (> 70% share) |
| **Secondary suppression** | Suppress additional cells to prevent back-calculation of primary suppressions |
| **Rounding** | Round values to nearest 100, 1000, etc. |
| **Data perturbation** | Small random adjustments to micro-data |

### Access to Confidential Data

Researchers may access confidential micro-data for scientific purposes:
- Via **Eurostat Safe Centre** (on-site access in Luxembourg)
- Via **Remote Access Facility** (remote access under strict controls)
- **Scientific Use Files**: Anonymised micro-data files for approved research

## Eurostat Database and Dissemination

### Publication Calendar

- Pre-announced release dates (binding commitment to punctuality)
- Embargo until official release time (typically 11:00 CET)
- Press releases for key publications (GDP, inflation, employment, trade)

### Database Structure

| Level | Example |
|-------|---------|
| **Theme** | Economy and finance, Population and social conditions, Industry and services |
| **Dataset** | bop_its6_det (ITSS detailed by partner, EBOPS) |
| **Dimensions** | Reporter, Partner, Service item (EBOPS), Flow (credit/debit), Currency, Adjustment |
| **Time** | Annual, quarterly |

### Metadata (ESMS)

Euro SDMX Metadata Structure:
- Contact information
- Statistical presentation
- Unit of measure
- Reference period
- Institutional mandate
- Confidentiality policy
- Release policy
- Frequency of dissemination
- Quality management
- Relevance, accuracy, timeliness, comparability, coherence

## Key Legal References

- **European Business Statistics Regulation (EU) 2019/2152**: Framework regulation
- **Regulation (EC) 223/2009**: European statistics, statistical confidentiality
- **BPM6 (IMF)**: Balance of Payments and International Investment Position Manual (6th edition)
- **MSITS 2010 (UN/WTO/OECD/IMF/Eurostat)**: Manual on Statistics of International Trade in Services
- **EBOPS 2010**: Extended Balance of Payments Services Classification
- **ESS Quality Framework**: Quality principles and indicators

## Cross-References

- See also: `eu_budget_emu_law.md` for European Semester data requirements
- See also: `european_semester_communication.md` for economic forecast methodology
- See also: `data_quality_query_template.md` for formal NSI query template
