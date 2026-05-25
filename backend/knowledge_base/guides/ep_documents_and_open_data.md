# European Parliament — Where the Documents and Data Live

## QUICK FACTS
- **What this is**: the map of EP data and document sources — so Brubru fetches from the right place (API first, scraping last) and cites correctly.
- **The machine-readable backend is the EP Open Data API** (`https://data.europarl.europa.eu/api/v2`): **339 datasets**, JSON-LD/RDF/CSV/TTL, OpenAPI 3, **rate limit 500 requests / 5 min per endpoint**, licence **CC BY 4.0**. The EP's equivalent of EUR-Lex's Cellar.
- **The EP website (`www.europarl.europa.eu`) is a JavaScript SPA** — prefer the API; if a page must be rendered, use the headless fetcher with a hard timeout (some EP pages hang the browser). See `docs/api/eu_parliament_data_access.md`.
- **Documents live on doceo** (`europarl.europa.eu/doceo/document/…`) with predictable references; **legislative procedures live on OEIL**.
- **Why Brubru cares**: votes, adopted texts, MEP/committee/group data and procedures feed Predictions, Position Analysis, the Legislative Tracker, My Files and chat answers.

## The EP Open Data API v2 (use this first)
- **Base**: `https://data.europarl.europa.eu/api/v2`; send `User-Agent: Brubru-prd-x.y.z`; respect 500 req / 5 min.
- **Endpoints**: `/meps` (+ `/{id}`, current, incoming/outgoing), `/corporate-bodies` (committees, groups, delegations), `/meetings`, `/adopted-texts`, `/procedures`, `/documents`. Param `parliamentary-term` 0–10.
- **339 datasets in 11 families**: Plenary Session Documents (188), Procedures (46), Plenary Documents (27), Committee documents (16), Texts Adopted (15), Questions & Answers (14), Meetings (13), MEPs (11), Speeches (6), Vote Results (2), Bodies (1) — all as RDF/XML, CSV, TTL.
- Brubru wraps it in `services/api_clients/ep_open_data_client.py`.

## doceo — the document store and its references
`europarl.europa.eu/doceo/document/…`, with constructible references (term 10 → `-10-`):
- **Plenary agenda**: `OJ-10-{YYYY-MM-DD}-SYN_EN.html`
- **Adopted texts**: `P10_TA(YYYY)NNNN`
- **Reports**: `A10-NNNN/YYYY`; **motions/resolutions**: `B10-NNNN/YYYY`; **joint motions**: `RC-B…`
- **Committee documents (PE-numbers)**: `PE` + digits + version (draft reports, amendments, opinions)
- **EP10 URL discipline**: on a 404, **switch tool** (Tavily / scraper output), never re-guess the path. See `feedback_ep_url_no_guessing`.

## OEIL — legislative procedures
The Legislative Observatory holds the **procedure file** for every dossier (basic info, key players, key events, documentation gateway, forecasts). Procedure refs like `2021/0106(COD)`. Working URL: `oeil.europarl.europa.eu/oeil/en/procedure-file?reference=…`; XML predefined-search exports for the latest procedures. See `docs/api/eu_legal_data_access.md` §7.

## The Public Register of Documents
`europarl.europa.eu/RegistreWeb/` — the EP's register under Regulation 1049/2001 (public access to documents), plus the historical archives and the "ask-EP" request form. Use for documents not exposed by the API.

## Other EP data surfaces
- **EPRS / Think Tank** (`/thinktank/en/`): research outputs by contributor (EPRS, STOA, EAVA, policy departments). Mandatory `/news` source.
- **Committee pages** (`/committees/en/{code}/…`): draft agendas, reports, amendments, votes, minutes — scraped via `committee_work_scraper.py`.
- **Multimedia Centre / webstreaming**: committee + plenary video (transcribed on demand).
- **EP Newshub, press releases, RSS** (`/at-your-service/en/stay-informed/rss-feeds`).

## How Brubru uses this (mapping data → features)
| EP data | Brubru feature |
|---|---|
| `/adopted-texts`, `/meetings/votes` | Predictions, Position Analysis |
| `/procedures` + OEIL | Legislative Tracker, My Files |
| Committee documents (doceo, PE-numbers) | Amendator, Amendments tab |
| `/meps`, `/corporate-bodies` | Chat context (who does what), group/committee membership |
| EPRS / Think Tank | Chat KB enrichment (`/news` Step 1d) |

**Fetch discipline**: API → OEIL/doceo/RSS → headless fetcher (subprocess-isolated, hard-capped) → Tavily. Never run an unbounded in-process render over EP SPA pages.

## Cross-references
- `european_parliament_structure.md` — the institution behind the data
- `ep_committees_overview.md` / `ep_political_groups_overview.md` — the bodies the data describes
- `finding_and_citing_eu_law.md` — the EUR-Lex/Cellar side of EU legal data
- `docs/api/eu_parliament_data_access.md` — the full EP engineering reference
- `services/api_clients/ep_open_data_client.py` — the API client; `committee_work_scraper.py` — committee docs
