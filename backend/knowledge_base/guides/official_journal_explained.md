# The Official Journal of the European Union — How EU Law Is Published

## QUICK FACTS
- **What it is**: the **Official Journal (OJ)** is the authentic publication of EU legal acts, published by the Publications Office **Monday–Friday in 24 languages** (and on weekends/holidays in urgent cases). Publication in the OJ is what gives an act legal effect.
- **Two series**: **L = Legislation** (regulations, directives, decisions) and **C = Information and notices** ("C" for the French *communications*).
- **e-OJ is authentic since 1 July 2013** (Council Regulation (EU) No 216/2013): only the electronic edition, with its electronic signature, has legal value. Verify authenticity with the **CheckLex** application.
- **Act-by-act publication since 1 October 2023** — the single biggest recent change: each act is now its **own** authentic OJ PDF; there is no longer a collated issue with a table of contents. This **forks every OJ link/identifier into pre- and post-Oct-2023 forms**.
- **Why Brubru cares**: the daily brief surfaces OJ-L substantive instruments; link construction, the `eu_laws` table, and freshness all depend on getting the OJ model right. Full reference: `docs/api/eu_legal_data_access.md`.
- **Source spec**: https://eur-lex.europa.eu/content/help/oj/about-oj.html (Publications Office).

## The series and historical subseries
| Series | Content |
|---|---|
| **L** | Legislation — binding acts. Discontinued subseries: **LI** (Isolated, since 2016), **LM** (Maltese backlog after 2004). |
| **C** | Information & notices — other documents from EU institutions/bodies. Discontinued: **CA** (Annex — vacancy notices), **CI** (Isolated), **CE** (Electronic, 1999–2014). |
| Historical | **A** (1952–58, *antérieur*), **P** (1958–67, *postérieur*) — acts before the modern series. |

## The 1 October 2023 act-by-act change (operational watershed)
Before 1 Oct 2023, the OJ was a collated issue (e.g. *OJ L 169, 25.6.2024*) with a table of contents; acts were addressed by series + issue number + page. After, **each act is published individually** as its own authentic OJ.

This changes the identifiers and links:
- **OJ number**: 3 digits (pre) → **5 digits** (post).
- **Post-Oct-2023 act link**: `…/legal-content/EN/TXT/?uri=OJ:L_202401987` (add `HTML`/`XML` for those views).
- **Pre-Oct-2023 act link**: `…/legal-content/EN/TXT/?uri=uriserv:OJ.L_.2016.352.01.0018.01.ENG` and TOC links `…?uri=OJ:C:2015:326:TOC`.

**Brubru rule**: any code or citation that builds an OJ link or parses an OJ reference must branch on this date.

## Numbering of acts (post-2015)
An act number has three parts: a **domain abbreviation** in brackets — `(EU)`, `(Euratom)`, `(EU, Euratom)`, `(CFSP)` — the **year** (4 digits), and a **sequential number**. So "Regulation (EU) 2024/1689". OJ-C notices: `C` + year + sequential.

## Authenticity (e-OJ)
- Only the **electronic edition** has legal value since 1 July 2013; paper has none (except documented IT-failure fallbacks).
- The e-OJ carries an electronic signature guaranteeing authenticity, integrity and inalterability.
- Verify via **CheckLex**: download the e-OJ PDF + its signature file, upload both, click Verify.

## Special editions
On accession, the in-force *acquis* is translated into the new Member State's language and compiled into **Special Editions** of the OJ, grouped into 20 chapters (matching the directory of legal acts).

## Linguistic coverage
24 official languages. Coverage of older acts depends on accession date (deepest for the founding languages DE/FR/IT/NL); Irish had transitional derogations until 31 Dec 2021. See `finding_and_citing_eu_law.md`.

## How Brubru uses the OJ model
- **Daily brief**: the OJ-today layer is pulled from Cellar SPARQL (`scripts/cellar_news_helper.py --oj-today`), not by scraping the WAF-walled `eur-lex.europa.eu/oj` page.
- **`eu_laws` table**: stores both the OJ reference and the CELEX for each publication.
- **Link emission**: prefer ELI (`eli_european_legislation_identifier.md`); when an OJ link is needed, branch on the act-by-act date.

## Cross-references
- `finding_and_citing_eu_law.md` — the hub guide
- `celex_number_format.md` — sector/year/type identifiers
- `eli_european_legislation_identifier.md` — the stable permalink to emit
- `eu_legislative_procedures_explained.md` — how an act reaches the OJ
- `docs/api/eu_legal_data_access.md` — engineering reference (OJ link taxonomy, views, formats)
