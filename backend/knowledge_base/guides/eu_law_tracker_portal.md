# EU Law Tracker (law-tracker.europa.eu): Post-Adoption Lifecycle Portal

## QUICK FACTS
- **URL:** https://law-tracker.europa.eu/homepage?lang=en
- **Run by:** Publications Office of the European Union (OP), built on the EUR-Lex/ELI technology stack
- **What it tracks:** Post-adoption lifecycle of adopted EU legal acts: entry into force dates, application dates, transposition deadlines for directives, amendments, consolidations, and repeals
- **Coverage:** All adopted EU legal acts with a CELEX number (regulations, directives, decisions, recommendations, etc.)
- **Act detail URL pattern:** `https://law-tracker.europa.eu/details/[CELEX]?lang=en`
  - AI Act example: `https://law-tracker.europa.eu/details/32024R1689?lang=en`
  - GDPR example: `https://law-tracker.europa.eu/details/32016R0679?lang=en`
  - NIS2 Directive example: `https://law-tracker.europa.eu/details/32022L2555?lang=en`
- **Language coverage:** All 24 official EU languages via the `lang=` parameter (e.g. `lang=fr`, `lang=nl`, `lang=es`, `lang=de`)
- **Underlying standard:** European Legislation Identifier (ELI) metadata -- see `eli_european_legislation_identifier`
- **Distinct from OEIL:** OEIL (European Parliament's procedure tracker) covers the pre-adoption legislative procedure only; the Law Tracker begins where OEIL ends, at adoption and Official Journal publication
- **Distinct from EPRS Legislative Train:** The EPRS Legislative Train tracks legislative status before adoption and provides political progress context; it stops at adoption; the Law Tracker covers post-adoption obligations only
- **Distinct from EUR-Lex:** EUR-Lex is the full-text official document repository; the Law Tracker is a structured lifecycle metadata layer on top of EUR-Lex, optimised for compliance monitoring rather than text retrieval
- **Primary use cases:** Compliance calendaring (when do obligations start?); transposition monitoring (by when must Member States implement a directive?); regulatory watch (has this law been amended or repealed?); identifying the current consolidated version of a legal act

---

## What the Law Tracker is

The EU Law Tracker is a dedicated portal published by the Publications Office of the European Union. Its purpose is to present the post-adoption lifecycle of EU legislation in a structured, searchable format derived from ELI (European Legislation Identifier) metadata.

Where EUR-Lex provides the full text of every Official Journal publication, the Law Tracker surfaces the lifecycle dates and relationships that matter most to compliance professionals, in-house legal teams, public affairs practitioners, and policy watchers. A user who needs to know when a regulation becomes applicable, when a directive's transposition deadline falls, or whether a legal act has subsequently been amended or repealed can find that information at a glance on the Law Tracker, without having to parse full legislative texts.

The portal is a JavaScript single-page application (SPA). All 24 official EU language versions are accessible by appending the `lang=` parameter to any URL. The underlying data is drawn from the same ELI-tagged metadata that powers EUR-Lex SPARQL endpoints and the Publications Office Open Data infrastructure (see `eu_publications_office_and_open_data`).

---

## URL Anatomy

The Law Tracker uses a consistent URL structure:

| Page | URL pattern |
|------|-------------|
| Homepage / search | `https://law-tracker.europa.eu/homepage?lang=en` |
| Act detail page | `https://law-tracker.europa.eu/details/[CELEX]?lang=en` |
| Language variant | Replace `lang=en` with any ISO 639-1 code (`fr`, `nl`, `es`, `de`, `it`, `pl`, etc.) |

The CELEX number is the standard identifier for every EU legal act. The format is: sector digit + year (4 digits) + type letter(s) + sequential number. For example:
- `32024R1689` = the AI Act (sector 3 = secondary law, 2024, R = regulation, 1689)
- `32016R0679` = the GDPR (sector 3, 2016, R = regulation, 0679)
- `32022L2555` = the NIS2 Directive (sector 3, 2022, L = directive, 2555)

To find the CELEX number for any act, see the guide `finding_and_citing_eu_law`.

---

## How the Law Tracker Differs from OEIL, the Legislative Train, and EUR-Lex

| Tool | Run by | Covers | Stops at | Primary use |
|------|--------|--------|----------|-------------|
| **EU Law Tracker** | Publications Office | Post-adoption lifecycle | Active/repealed | Compliance calendaring; transposition monitoring; amendment tracking |
| **OEIL** | European Parliament | Pre-adoption legislative procedure | Adoption | Tracking political progress; procedure type; rapporteur; committees involved |
| **EPRS Legislative Train** | EP Research Service | Pre-adoption status + political context | Adoption | High-level overview of where a file sits in the legislative cycle |
| **EUR-Lex** | Publications Office | Full text of all OJ acts + pre-adoption documents | Ongoing | Reading the text; finding recitals; downloading XML/PDF |

Key distinctions in practice:

**OEIL ends at adoption; Law Tracker begins at adoption.** If a user asks "has the AI Act been amended since adoption?", OEIL cannot help -- it covers only the original 2021-2024 legislative procedure. The Law Tracker shows any amending acts published after OJ publication.

**The EPRS Legislative Train provides political colour; the Law Tracker provides compliance dates.** A practitioner tracking the Data Governance Act for a client compliance report needs application dates and delegated-act deadlines, not the rapporteur's political position -- that is a Law Tracker query.

**EUR-Lex is text-first; the Law Tracker is lifecycle-first.** Both are run by the Publications Office on the same ELI stack. Use EUR-Lex when you need recitals, articles, and document metadata. Use the Law Tracker when you need structured lifecycle events without navigating the full document.

---

## What Lifecycle Data is Exposed

A typical Law Tracker detail page for a given CELEX number exposes the following structured data:

**Dates**
- Date of signature or adoption
- Date of entry into force (the 20th day after OJ publication for most regulations, unless the act specifies otherwise)
- Date of application (frequently later than entry into force; for example, the AI Act entered into force in August 2024 but most obligations apply from August 2026)
- Transposition deadline (directives only; the date by which Member States must incorporate the directive into national law)
- Review dates (if the act specifies a mandatory review clause)
- End date / date of repeal (if the act has been superseded)

**Relationships**
- Amending acts: subsequent OJ publications that modified the original text (identified by CELEX)
- Consolidated versions: the corrigendum/consolidation maintained by the Publications Office showing the act as currently in force
- Replacing acts: the act that repealed and replaced the one being viewed
- Related implementing or delegated acts (where ELI metadata captures these links)

**Status**
- In force
- Partially in force (some provisions apply, others do not yet)
- Expired / repealed
- Replaced

---

## Practical Chat-Routing Rule

Use the following decision tree when a user question could involve any of the three trackers:

**If the question is "where are we in the legislative procedure?" or "has this proposal been adopted?"**
Route to OEIL (see `legislative_train_observatory` for the EPRS Legislative Train equivalent). The Law Tracker is not the right tool.

**If the question is "when does this regulation apply?" or "what is the transposition deadline for this directive?" or "has this law been amended?"**
Route to the EU Law Tracker at `https://law-tracker.europa.eu/details/[CELEX]?lang=en`. Provide the direct URL with the CELEX substituted.

**If the question is "what does Article X say?" or "show me the text of this directive"**
Route to EUR-Lex at `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:[CELEX]`. The Law Tracker does not render legislative text.

**If the question is about transposition compliance -- whether a specific Member State has actually transposed a directive**
The Law Tracker shows the EU-level transposition deadline but does NOT track individual Member State transposition status. For that, route to the Commission's infringement procedure records (see `eu_law_application_monitoring`) or the EUR-Lex national implementation search.

**If the question is about ELI URIs or machine-readable metadata**
See `eli_european_legislation_identifier` and `eu_publications_office_and_open_data`.

---

## High-Priority Acts to Know on the Law Tracker

These are acts that compliance professionals and policy practitioners frequently track; the Law Tracker is the fastest way to retrieve their key lifecycle dates:

| Act | CELEX | Entry into Force | Key Application Date |
|-----|-------|-----------------|----------------------|
| AI Act | 32024R1689 | 1 August 2024 | 2 August 2026 (most obligations); 2 August 2025 (prohibitions); 2 August 2027 (GPAI rules) |
| GDPR | 32016R0679 | 24 May 2016 | 25 May 2018 |
| DSA | 32022R2065 | 16 November 2022 | 17 February 2024 (all platforms) |
| DMA | 32022R1925 | 1 November 2022 | 2 May 2023 |
| NIS2 Directive | 32022L2555 | 16 January 2023 | Transposition deadline: 17 October 2024 |
| CSRD | 32022L2464 | 5 January 2023 | Transposition deadline: 6 July 2024; first reports 2025 |
| CBAM Regulation | 32023R0956 | 17 May 2023 | Transitional: 1 October 2023; full: 1 January 2026 |
| Data Governance Act | 32022R0868 | 23 June 2022 | 24 September 2023 |

Note: Application dates above are drawn from the legislative text. Always verify against the Law Tracker for the act's current consolidated status and any subsequent amendments.

---

## Limitations

**Post-adoption only.** The Law Tracker has no data on proposals, amendments under negotiation, or procedures that have not yet reached the Official Journal. For in-progress files, use OEIL or the EPRS Legislative Train.

**Relies on ELI metadata completeness.** The portal depends on the Publications Office correctly tagging each act with its lifecycle events in ELI format. Older acts (pre-2000) may have incomplete or absent lifecycle metadata. Consolidated versions are produced on a best-efforts basis and are not legally binding.

**No Member State transposition tracking.** The portal shows when Member States were required to transpose a directive, not whether they did so. Transposition compliance data is held by the Commission and surfaced via infringement proceedings (see `eu_law_application_monitoring`) and the Single Market Scoreboard.

**JavaScript SPA.** The portal cannot be scraped without a browser (it returns template placeholders to plain HTTP clients). Programmatic access to the underlying ELI data is better achieved via EUR-Lex SPARQL or the Publications Office open data APIs (see `eu_publications_office_and_open_data`).

**No legislative history before adoption.** The consolidation history shows post-adoption amendments only. For the full negotiating history (Council positions, EP first-reading amendments, trilogue documents), use EUR-Lex or OEIL.

**Language display vs. legal force.** The language toggle changes the interface language and some metadata labels; the definitive legal text in each Official Journal language is the EUR-Lex authentic version, not the Law Tracker display.

---

## Related Guides

- `eli_european_legislation_identifier` -- the ELI metadata standard that underpins the Law Tracker
- `finding_and_citing_eu_law` -- how to locate CELEX numbers and EUR-Lex URIs
- `eu_law_application_monitoring` -- Commission's annual report on Member State transposition and Article 258 TFEU infringement procedures
- `eu_publications_office_and_open_data` -- the Publications Office infrastructure, open data APIs, and EUR-Lex machine-readable access
- `legislative_train_observatory` -- the EPRS Legislative Train for pre-adoption procedure tracking
