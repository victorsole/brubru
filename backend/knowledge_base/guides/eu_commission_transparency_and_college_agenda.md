# EU Commission Transparency — College Agenda, Corporate-Body Codes, Lobby Register

## QUICK FACTS
- **What this is**: the transparency/registry surfaces of the Commission and how to read them — the **College tentative agenda**, the **corporate-body authority codes** (how bodies are tagged), the **lobby-meeting register**, **expert groups**, and **WhoisWho**.
- **College agendas** live in the **Transparency documents-register**, not on a tidy calendar page: search type **`TENTAT_AGENDA_COM_MEETING`** (tentative agenda) and **`PV`** (minutes). This is the **authoritative source** for what the College will adopt — verify College dates here, never from trade press.
- **The corporate-body code** (`http://publications.europa.eu/resource/authority/corporate-body/{CODE}`) is the join key: it tags Commission news, publications and acts by author body (AGRI, CNECT, COMP, SANTE…). 53 codes catalogued in `docs/api/eu_commission_data_access.md`.
- **Why Brubru cares**: this powers truthful College-date claims (brief/news/calendar), author-filtered news feeds, and DG→acts joins.
- **Source**: `ec.europa.eu/transparency/...` + `publications.europa.eu/.../who-is-who` (read 31 May 2026).

## The College tentative agenda (the "what's coming" source)
- **Where**: `ec.europa.eu/transparency/documents-register/search?query=<base64-JSON>`. The query string is base64-encoded JSON describing the filter; type **`TENTAT_AGENDA_COM_MEETING`** returns the College's tentative agendas; **`PV`** returns adopted minutes.
- **Reading it**: a tentative-agenda item dated "(tbc)" is **not** a confirmed adoption — hedge. Packages slip (the Tech Sovereignty Package moved across several dates in 2026). The highest `SEC(YYYY)NNNN` is the live agenda.
- **Engineering**: this is a **JS single-page app** — a plain fetch returns an empty shell. Render with `services/scrapers/waf_browser_fetcher.py` (subprocess-isolated + hard timeout). Curl/requests is 202/empty.

## Corporate-body authority codes (the join key)
`http://publications.europa.eu/resource/authority/corporate-body/{CODE}` tags every Commission output by author body. Used to:
- filter **news** (`commission.europa.eu/news_en?f[0]=departments_departments:…/corporate-body/{CODE}`),
- filter **publications/Management Plans/AARs** (`oe_publication_authors:…/corporate-body/{CODE}`),
- look up the **WhoisWho** entry (`publications.europa.eu/en/web/who-is-who/organization/-/organization/{CODE}`),
- and **join a DG to its acts** in Cellar (same authority scheme EUR-Lex uses — see `eu_legal_data_access.md`).
Codes include the DGs (AGRI, BUDG, CLIMA, CNECT, COMP, DEFIS, ECFIN, EAC, EMPL, ENER, ENEST, ENV, ESTAT, FISMA, GROW, HOME, INTPA, JRC, JUST, MARE, MENA, MOVE, REGIO, RTD, SANTE, TAXUD, TRADE), the services (SG, SJ, DGT, SCIC, COMMU, HR, DIGIT, IAS, OIB, OLAF, FPI, HERA, PUBL, REFOR) and the executive agencies (CINEA, EACEA, EISMEA, ERCEA, HADEA, REA).

## The lobby-meeting register (who met whom)
- **Where**: `ec.europa.eu/transparency-initiative/meetings/meeting.do?host={uuid}`. Every DG and Commissioner cabinet has a **host id**; the register lists meetings with **registered interest representatives** (linked to the EU Transparency Register).
- **Use**: signals on which files a DG is actively consulting industry on. JS-SPA — render with the WAF fetcher.

## Expert groups & comitology
- **Expert groups register**: `ec.europa.eu/transparency/expert-groups-register/...` — the advisory groups that feed Commission drafting; membership and meeting documents are listed.
- These differ from **comitology committees** (Member State representatives scrutinising implementing/delegated acts).

## Other transparency surfaces
- **Financial Transparency System (FTS)**: `ec.europa.eu/budget/financial-transparency-system` — who receives directly-managed EU funds.
- **WhoisWho**: the official EU staff/organisation directory (per corporate-body code).
- **Have Your Say**: public consultations + feedback (see `eu_commission_decision_making.md`).

## Connection to Brubru's hard rule
Brubru already mandates verifying any College date/announcement against the **EC Transparency Register tentative-agenda** before asserting it in a brief, post, guide or calendar. This guide is the *what/where*; the *how* (Playwright → api/files → pdftotext recipe; the two canonical search URLs) lives in the operational memory.

## Cross-references
- `european_commission_who_does_what.md` — the bodies behind the codes
- `eu_commission_decision_making.md` — the College + Have Your Say
- `eu_legal_data_access.md` — DG → corporate-body → acts in Cellar
- `docs/api/eu_commission_data_access.md` — §3 codes, §8 agendas/transparency
