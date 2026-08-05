# Team Europe Explorer and IATI Reporting

## QUICK FACTS
- **"Team Europe":** the joint external-action approach bringing together the EU institutions, the 27 EU Member States, the European Investment Bank (EIB) and the European Bank for Reconstruction and Development (EBRD) to act as one coordinated actor abroad rather than as parallel bilateral donors
- **Team Europe Explorer:** public web platform at https://team-europe-explorer.europa.eu/ visualising EU and Member-State Official Development Assistance (ODA) and Total Official Support for Sustainable Development (TOSSD) spending -- "the only platform where you can visualise both the EU and its 27 Member States' spending" of these aid categories
- **Replaced:** EU Aid Explorer, the Commission's previous aid-transparency portal. Team Europe Explorer keeps everything EU Aid Explorer offered and adds TOSSD data plus a Team Europe-wide (EU + Member States + EIB + EBRD) view
- **Underlying open-data standard:** IATI (International Aid Transparency Initiative), a global initiative improving transparency of development and humanitarian resources; publishers disclose activity- and organisation-level data under the IATI Standard (Activity Standard + Organisation Standard)
- **EU/Commission IATI reporting-organisation identifier: `XM-DAC-918`** -- the identifier under which the European Commission publishes its development and international-cooperation activities to IATI. Use this identifier as the `reporting-org` filter value when querying the IATI Datastore for Commission-financed activities
- **IATI Datastore:** https://iatistandard.org/en/iati-tools-and-resources/iati-datastore/ -- a single queryable index of everything published to the IATI Standard by all publishers worldwide (over 1,800 publishers, 1M+ activities). Exports as JSON, XML, CSV or Excel; API access via the IATI developer platform (API key required, see "How to use the Datastore API")
- **Data sources feeding Team Europe Explorer:** Commission internal financial-management data (daily updates), EIB data (annual), OECD Creditor Reporting System (CRS) data reported by Member States, IATI-published data from Member States that report via IATI, and OECD TOSSD data (cross-border flows, global public goods)
- **Multi-annual Indicative Programmes (MIPs):** the programming layer under NDICI-Global Europe and IPA III that sets country/region and thematic spending envelopes for a multi-year period (2021-2024, 2025-2027); MIPs are the plan, Team Europe Explorer and IATI are the reporting/actuals layer that shows what was actually disbursed against that plan
- **Team Europe Initiatives (TEIs):** flagship joint packages combining EU budget, Member State bilateral contributions and DFI financing around a single strategic objective (for example digital connectivity, green energy corridors, health-system resilience) in a partner country or region. The Commission calls TEIs an example of "how coming together in a Team Europe approach can deliver transformational results"
- **Relevance to Brubru's financial-data spine (`data/financial_data.md`):** Team Europe Explorer/IATI is the beneficiary/recipient trail for **external action** money, structurally parallel to Kohesio (cohesion beneficiaries, internal EU) and CORDIS (Horizon Europe research beneficiaries). Together they let the spine answer "where does EU money land" across internal cohesion, research and external development in one join
- **Data caveats:** reporting lag varies by data source (Commission internal data is daily, Member-State IATI/CRS reporting can lag months); aggregation level varies -- some flows are visible only at country/sector/year level, not per named beneficiary company or NGO; TOSSD and ODA use different eligibility rules, so totals are not directly additive across the two; IATI publisher data quality varies by Member State (not all 27 report at the same granularity or frequency)

> For the legal instrument behind most of this spending, see `ndici_global_europe_instrument.md` (NDICI-Global Europe, Regulation (EU) 2021/947) and `ipa_iii_pre_accession_assistance.md` (planned, pre-accession spending outside NDICI's scope). For the blended-finance/guarantee layer, see `efsd_plus_external_action_guarantee.md` (planned). For the Commission service that runs most of this, see `dg_intpa_overview.md`. For the flagship strategy these flows help finance, see `global_gateway_strategy.md`. For the internal-EU cohesion-beneficiary equivalent, see `kohesio_cohesion_beneficiaries_database.md` (planned). For the research-beneficiary equivalent, see `cordis_research_projects_database.md`. For the general open-data catalogue infrastructure this sits alongside, see `data_europa_eu_open_data_portal.md`.

---

## What "Team Europe" means

"Team Europe" is not a legal entity or a new institution. It is a coordination label the EU adopted, especially since the COVID-19 response of 2020, to present EU institutional spending, EU Member State bilateral spending, and financing from the EU's own development finance institutions as one combined external-action effort rather than dozens of uncoordinated national programmes running alongside a separate Commission programme.

The four constituent actors are:

1. **EU institutions** -- chiefly the European Commission (via NDICI-Global Europe, IPA III, and thematic instruments) and the European External Action Service (EEAS), which provides the political and diplomatic steer through EU Delegations in partner countries.
2. **The 27 EU Member States** -- through their national development agencies and bilateral aid programmes (for example AFD for France, GIZ/KfW for Germany, AECID for Spain).
3. **The European Investment Bank (EIB)** -- the EU's house bank, financing infrastructure and private-sector projects globally, including outside the EU's own borders.
4. **The European Bank for Reconstruction and Development (EBRD)** -- though not an EU body (it has non-EU shareholders including the UK, US and others), the EU and its Member States are majority shareholders and the EBRD is treated as a Team Europe partner for financing in its countries of operation.

The practical effect: an EU Delegation in a partner country coordinates what the Commission, the Member States present, the EIB and (where relevant) the EBRD are each doing, so that joint packages can be assembled instead of five separate uncoordinated donor programmes competing for the same government's attention.

---

## Team Europe Explorer: the portal (replaced EU Aid Explorer)

**URL:** https://team-europe-explorer.europa.eu/

Team Europe Explorer is the Commission's public visualisation platform for EU and Team Europe development and international-cooperation spending. It replaced the older **EU Aid Explorer** portal, carrying forward everything EU Aid Explorer offered (Commission ODA flows by country, sector and year) while adding two things EU Aid Explorer did not have:

1. **A Team Europe-wide view** -- spending by the 27 Member States and the EIB alongside the Commission's own figures, not just Commission spending in isolation.
2. **TOSSD data** -- Total Official Support for Sustainable Development, an OECD-defined measure broader than traditional ODA, capturing cross-border flows and support for global public goods (climate, health security, biodiversity) that classic ODA accounting can miss.

The portal presents data through graphs and interactive maps answering three recurring questions: which actor is active where, how much financial support a given geography or theme receives, and how funding changes year on year. It is aimed at partner-country governments, civil society, journalists, researchers and other donors wanting to see the full Team Europe footprint in one place rather than piecing it together from 28+ separate national reporting systems.

Because the underlying data comes from multiple pipelines with different update cadences (Commission internal data daily, EIB annually, OECD CRS and IATI on their own publication schedules), users should treat the most granular, most recent figures as provisional until reconciled against the annual OECD DAC statistical release.

---

## The IATI standard and the Commission's XM-DAC-918 identifier

**IATI (International Aid Transparency Initiative)**, at https://iatistandard.org/, is a global multi-stakeholder initiative (governments, multilateral institutions, private-sector and civil-society organisations) that defines a common open-data standard for publishing development and humanitarian activity data. It has two documentation tracks: the **Activity Standard** (project/programme-level data: title, sector, budget, transactions, results, location) and the **Organisation Standard** (publisher-level data: total budgets, expenditure, document links).

Every organisation that publishes to IATI does so under a unique **reporting-organisation identifier**, generally following the pattern `{country-code}-{registration-agency}-{registration-number}` (for DAC members this is typically `XM-DAC-{number}`, where `XM` is the ISO code used for multilateral/supranational reporters and `DAC` marks the OECD Development Assistance Committee registration agency).

**The European Commission's IATI reporting-organisation identifier is `XM-DAC-918`.** All Commission-financed development and international-cooperation activities that are published to IATI carry this identifier as their `reporting-org` value, which is what allows anyone -- Brubru included -- to isolate Commission-financed activities inside the wider IATI dataset without needing a bespoke Commission feed.

---

## How to query flows: the IATI Datastore and API

**IATI Datastore:** https://iatistandard.org/en/iati-tools-and-resources/iati-datastore/

The Datastore aggregates everything published under the IATI Standard by every publisher worldwide into a single queryable index (well over a million activities from 1,800+ publishers). It offers:

- **Datastore Search** -- a browser search UI for non-technical users, exporting results as CSV or Excel.
- **Datastore API** -- programmatic access for developers, returning activity, budget or transaction-level records as JSON or XML, filterable by reporting organisation, recipient country, sector, transaction type, activity status and date range.

**Practical query pattern for NDICI/IPA III flows:** filter the Datastore API (or Datastore Search) on the reporting-organisation identifier `XM-DAC-918` to scope to Commission-financed activities, then narrow further by recipient-country code (ISO), sector code (typically OECD CRS purpose codes), and year, to reconstruct which NDICI or IPA III-financed activities reached a given country or sector in a given year. Access requires an API key issued through the IATI developer platform (`developer.iatistandard.org`); the exact endpoint paths and filter-parameter names are documented in IATI's own "How to use the Datastore API" guide and API contract, since these can change between Datastore API versions.

Because Team Europe Explorer itself blends Commission-internal data with IATI-published data (rather than being a pure IATI front end), the two surfaces will not always show identical figures for the same activity: Team Europe Explorer's Commission-internal feed updates daily and can be more current than what a given IATI publication cycle has captured.

---

## MIPs and Team Europe Initiatives: the programming layer above the reporting layer

**Multi-annual Indicative Programmes (MIPs)** are the planning documents that sit above the reporting data. Under NDICI-Global Europe and IPA III, the Commission (with the EEAS for geographic programmes) adopts a MIP for each partner country, region, or thematic programme, indicating the priority sectors and the indicative financial envelope for a multi-year period (the current cycle runs 2021-2024 and 2025-2027). MIPs answer "what is planned"; Team Europe Explorer and IATI answer "what was actually disbursed."

**Team Europe Initiatives (TEIs)** are the flagship joint packages built on top of MIP priorities, combining Commission funding, Member State bilateral contributions, and EIB/EBRD financing around one strategic objective in a partner country or region (examples include digital connectivity corridors, green energy transitions, and health-system resilience packages). TEIs are the visible, branded expression of the Team Europe approach; MIPs are the underlying multi-year budget plan; Team Europe Explorer/IATI is where the actual money-moved data can be checked against both.

---

## Relevance to Brubru's financial-data spine

Brubru's financial/corporate-intelligence spine work (see `data/financial_data.md`) is built around a single join: **company -> every euro of EU money it touched -> the sectors and laws moving around it.** That spine currently anchors on the beneficiary trio for spending *inside* the EU (cohesion funds via Kohesio, state aid via DG COMP, tender awards via TED).

Team Europe Explorer and the IATI Datastore under `XM-DAC-918` are the structurally equivalent trail for money moving *outside* the EU under external action:

- **Kohesio** (planned guide `kohesio_cohesion_beneficiaries_database.md`) names beneficiaries of cohesion policy inside the EU.
- **CORDIS** (`cordis_research_projects_database.md`) names beneficiaries of Horizon Europe research funding.
- **Team Europe Explorer / IATI** names (where reporting granularity allows) the recipient countries, sectors, channels and, for some activities, implementing partners and projects funded under NDICI-Global Europe and IPA III.

Adding this surface lets the spine eventually answer "which EU external-action money has touched a given country, sector or implementing partner" alongside the existing internal-EU beneficiary picture, completing the picture across cohesion, research and external action.

---

## Data caveats

- **Reporting lag varies by source.** Commission internal financial-management data updates daily; EIB contributions update annually; OECD CRS and IATI-published Member State data follow their own publication calendars, which can lag by months.
- **Aggregation level is inconsistent.** Some flows are only visible at country/sector/year aggregate level; named beneficiary or implementing-partner detail is not guaranteed for every activity or every reporting Member State.
- **ODA and TOSSD are not additive.** They use different eligibility and accounting rules (TOSSD is broader, covering some flows ODA excludes); do not sum them into a single "total Team Europe spend" figure without checking which measure each row uses.
- **Member State reporting quality varies.** Not all 27 Member States report to IATI at the same frequency or granularity; some rely primarily on OECD CRS reporting instead, which has coarser detail than IATI's activity-level standard.
- **XM-DAC-918 scopes Commission activities, not all Team Europe activities.** Filtering the IATI Datastore on this identifier isolates Commission-financed flows only; capturing the full Team Europe picture (Member States + EIB + EBRD) requires combining this with Team Europe Explorer's own blended dataset or the separate IATI publisher identifiers used by individual Member State agencies and the EIB.

---

## Brubru tracking angles

- **Country/sector drilldown:** track NDICI/IPA III-financed activity by recipient country and sector using the `XM-DAC-918` filter, to answer "how much EU external-action money is flowing to sector X in country Y this year."
- **MIP-to-actuals reconciliation:** compare a country or region's Multi-annual Indicative Programme envelope against actual disbursed flows reported through Team Europe Explorer/IATI, surfacing under- or over-delivery against plan.
- **TEI monitoring:** where a Team Europe Initiative names specific implementing partners or projects, cross-reference against IATI activity records to track delivery of flagship joint packages.
- **Spine join:** feed recipient-country/sector/year records into the financial-data spine as the external-action leg, alongside Kohesio (cohesion) and CORDIS (research), so Chat and future spine-based products can answer "where does EU money land" across all three domains from one query.
- **Freshness signal:** use the daily-updated Commission-internal feed inside Team Europe Explorer as a faster-moving companion to the naturally slower IATI Datastore refresh cycle when near-real-time figures matter more than full Team Europe-wide coverage.
