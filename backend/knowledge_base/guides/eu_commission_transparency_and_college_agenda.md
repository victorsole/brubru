# EU Commission Transparency: College Agenda, Corporate-Body Codes, Lobby Register

## QUICK FACTS
- **LATEST (15 September 2026): what the College plans next, from the newest primary documents.** Live agenda: **SEC(2026) 2578 final, 14 September 2026**, horizon 30 September to 28 October 2026. Every date is **(tbc)**; hedge as "the Commission currently plans".

| College date (tbc) | Item | Responsible |
|---|---|---|
| Tue 15 Sep 2026, Strasbourg (from SEC(2026) 2577, 8 Sep) | **Child safety online** | President |
| Tue 15 Sep 2026, Strasbourg (from SEC(2026) 2577) | **Fair labour mobility package**: proposal for a European Social Security Pass; strengthening the European Labour Authority; skills portability initiative | EVP Mînzatu |
| Wed 30 Sep 2026 | Pre-enlargement policy reviews | President |
| Wed 30 Sep 2026 | European critical communication system | EVP Virkkunen |
| Wed 30 Sep 2026 | 2040 vision for fisheries and aquaculture | EVP Fitto |
| Tue 6 Oct 2026, Strasbourg | **European product package**: European Product Act (update of the framework for product rules and market surveillance) + Standardisation Regulation (update of rules on standardisation) | EVP Séjourné |
| Tue 20 Oct 2026, Strasbourg | **2027 Commission work programme** | President |
| Tue 20 Oct 2026, Strasbourg | 2026 annual overview report on simplification, implementation and enforcement | President |
| Tue 20 Oct 2026, Strasbourg | Northern Neighbourhood: **New Arctic Strategy** | President |
| Tue 20 Oct 2026, Strasbourg | **Enlargement package** | President |
| Tue 20 Oct 2026, Strasbourg | Climate resilience framework | EVP Ribera |
| Wed 28 Oct 2026 | **Border and migration package**: strengthening Frontex and enhancing its operations; digitalisation of the return process; European annual asylum and migration report | EVP Virkkunen |

- **Today, 15 September 2026 (Strasbourg College)**: child safety online and the fair labour mobility package are the planned items. **As of the morning of 15 September no Commission press release confirmed adoption** of either (Commission press corner and DG EMPL news checked). The EP agenda does hold a **scrutiny session "Presentation of the Fair Labour Mobility Package" on Tuesday 15 September, 15:00-16:00** (https://www.europarl.europa.eu/doceo/document/OJ-10-2026-09-14-SYN_EN.html). Press reports (Reuters, POLITICO, 14-15 Sep) say the child-protection proposal, which they call an "EU Kids Act", would be presented on Thursday 17 September: **press, and in conflict with the tentative agenda date**. Say "planned", not "adopted", until a Commission press release exists.
- **Last College held: 2577th meeting, Wednesday 9 September 2026, Brussels** (agenda OJ(2026) 2577 final, 8 Sep 2026). B items: **Affordable Housing Act** (proposal for a Regulation, COM(2026) 599, presented by Commissioner **Jørgensen in agreement with EVP Ribera**); **Public Procurement Act** (proposal for a Regulation on public contracts and concessions repealing the 2014 procurement directives, COM(2026) 590, EVP Séjourné); **European Innovation Act** (COM(2026) 567, Commissioner Zaharieva in agreement with EVP Séjourné); **Outermost Regions**: Communication "Strengthening the Union's Global Reach: A New Strategic Vision for the EU's Outermost Regions" (COM(2026) 660) plus a proposal for a Council Regulation adapting requirements and reducing administrative burden in the outermost regions (COM(2026) 661), both EVP Fitto, finalised by written procedure with a deadline of 10:00 on 10 September. Approval of the minutes of the 2575th (17 July) and 2576th (22 July) meetings was **held over**. Adoption of the housing, procurement and innovation proposals was confirmed by Commission press releases on 9 September, and the outermost regions Communication on 10 September (Commission press corner).
- **Slippage since SEC(2026) 2576 (20 July)**: the Affordable Housing Act was adopted on **9 September**, not 15 September as an earlier plan had it; the European Product Act moved from 30 September to **6 October**; strengthening Frontex moved from 30 September into the **28 October** border and migration package; the supply-chain dependencies proposal (aluminium scrap) previously pencilled for 23 September **no longer appears**; child safety online and the 2040 fisheries and aquaculture vision are **new** entries.
- **What this is**: the transparency/registry surfaces of the Commission and how to read them: the **College tentative agenda**, the **corporate-body authority codes** (how bodies are tagged), the **lobby-meeting register**, **expert groups**, and **WhoisWho**.
- **College agendas** live in the **Transparency documents-register**, not on a tidy calendar page: search type **`TENTAT_AGENDA_COM_MEETING`** (tentative agenda) and **`PV`** (minutes). This is the **authoritative source** for what the College will adopt: verify College dates here, never from trade press.
- **The corporate-body code** (`http://publications.europa.eu/resource/authority/corporate-body/{CODE}`) is the join key: it tags Commission news, publications and acts by author body (AGRI, CNECT, COMP, SANTE…). 53 codes catalogued in `docs/api/eu_commission_data_access.md`.
- **Why Brubru cares**: this powers truthful College-date claims (brief/news/calendar), author-filtered news feeds, and DG→acts joins.
- **Source**: `ec.europa.eu/transparency/...` + `publications.europa.eu/.../who-is-who` (read 31 May 2026).

## The College tentative agenda (the "what's coming" source)
- **Where**: `ec.europa.eu/transparency/documents-register/search?query=<base64-JSON>`. The query string is base64-encoded JSON describing the filter; type **`TENTAT_AGENDA_COM_MEETING`** returns the College's tentative agendas; **`PV`** returns adopted minutes.
- **Reading it**: a tentative-agenda item dated "(tbc)" is **not** a confirmed adoption: hedge. Packages slip (the Tech Sovereignty Package moved across several dates in 2026). The highest `SEC(YYYY)NNNN` is the live agenda.
- **Engineering**: this is a **JS single-page app**: a plain fetch returns an empty shell. Render with `services/scrapers/waf_browser_fetcher.py` (subprocess-isolated + hard timeout). Curl/requests is 202/empty.

## Corporate-body authority codes (the join key)
`http://publications.europa.eu/resource/authority/corporate-body/{CODE}` tags every Commission output by author body. Used to:
- filter **news** (`commission.europa.eu/news_en?f[0]=departments_departments:…/corporate-body/{CODE}`),
- filter **publications/Management Plans/AARs** (`oe_publication_authors:…/corporate-body/{CODE}`),
- look up the **WhoisWho** entry (`publications.europa.eu/en/web/who-is-who/organization/-/organization/{CODE}`),
- and **join a DG to its acts** in Cellar (same authority scheme EUR-Lex uses: see `eu_legal_data_access.md`).
Codes include the DGs (AGRI, BUDG, CLIMA, CNECT, COMP, DEFIS, ECFIN, EAC, EMPL, ENER, ENEST, ENV, ESTAT, FISMA, GROW, HOME, INTPA, JRC, JUST, MARE, MENA, MOVE, REGIO, RTD, SANTE, TAXUD, TRADE), the services (SG, SJ, DGT, SCIC, COMMU, HR, DIGIT, IAS, OIB, OLAF, FPI, HERA, PUBL, REFOR) and the executive agencies (CINEA, EACEA, EISMEA, ERCEA, HADEA, REA).

## The lobby-meeting register (who met whom)
- **Where**: `ec.europa.eu/transparency-initiative/meetings/meeting.do?host={uuid}`. Every DG and Commissioner cabinet has a **host id**; the register lists meetings with **registered interest representatives** (linked to the EU Transparency Register).
- **Use**: signals on which files a DG is actively consulting industry on. JS-SPA: render with the WAF fetcher.

## Expert groups & comitology
- **Expert groups register**: `ec.europa.eu/transparency/expert-groups-register/...`: the advisory groups that feed Commission drafting; membership and meeting documents are listed.
- These differ from **comitology committees** (Member State representatives scrutinising implementing/delegated acts).

## Other transparency surfaces
- **Financial Transparency System (FTS)**: `ec.europa.eu/budget/financial-transparency-system`: who receives directly-managed EU funds.
- **WhoisWho**: the official EU staff/organisation directory (per corporate-body code).
- **Have Your Say**: public consultations + feedback (see `eu_commission_decision_making.md`).

## Connection to Brubru's hard rule
Brubru already mandates verifying any College date/announcement against the **EC Transparency Register tentative-agenda** before asserting it in a brief, post, guide or calendar. This guide is the *what/where*; the *how* (Playwright → api/files → pdftotext recipe; the two canonical search URLs) lives in the operational memory.

## Cross-references
- `european_commission_who_does_what.md`: the bodies behind the codes
- `eu_commission_decision_making.md`: the College + Have Your Say
- `eu_legal_data_access.md`: DG → corporate-body → acts in Cellar
- `docs/api/eu_commission_data_access.md`: §3 codes, §8 agendas/transparency
