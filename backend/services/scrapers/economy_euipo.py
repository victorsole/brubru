"""
EUIPO — European Union Intellectual Property Office (api_market.md).
/api/v2/euipo.

EUIPO runs an anti-bot Material-UI SPA (euipo.europa.eu): no RSS, no server-side
content, headless renders are blocked. The SPA's listings are powered by a
public Algolia search index, which we call directly (the search-only key is the
one the site ships to browsers). Each hit already carries the full body, so no
detail fetch is needed. Source map (verified):
  - news   : Algolia index ews-en-news   (title, summary, body, fullSlug, date ms).
  - events : Algolia index ews-en-events  (title, summary, body, fullSlug, startDate ms).

EUIPO Observatory publications are served from a separate CMS with no public
search index, so only news + events are surfaced. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, norm_url, _BODY_CAP, _iso_dt, extract_html

_APP = "ZYN8P9OCP2"
_KEY = "428a6eab6ad825546f741c199084e245"  # public search-only key shipped by the EUIPO site
_SITE = "https://www.euipo.europa.eu/"
_INDEXES = {"news": ("ews-en-news", "date"), "event": ("ews-en-events", "startDate")}
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")

# Curated about + IP-domain landing pages. euipo.europa.eu is a JS SPA, so these
# are rendered through Playwright (local refresh / cron with Chromium).
_TOPIC_PATHS = [
    "en/about-us/the-office",
    "en/about-us/governance",
    "en/about-us/governance/strategic-plan",
    "en/about-us/the-office/what-we-do/quality",
    "en/trade-marks",
    "en/designs",
    "en/law",
    "en/guidelines",
    "en/boards-of-appeal",
    "en/mediation-centre",
    "en/observatory",
    "en/observatory/enforcement",
    "en/observatory/publications",
    "en/copyright-knowledge-centre",
    "en/sme-corner",
    "en/sme-corner/sme-fund",
    "en/enforce-ip/ip-enforcement-portal",
    "en/getting-started",
]


async def _scrape_topics_async(*, fetch_bodies: bool) -> list[Item]:
    from playwright.async_api import async_playwright
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        for path in _TOPIC_PATHS:
            url = norm_url(_SITE + path)
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(1800)
            except Exception:
                continue
            if resp is None or resp.status != 200:
                continue
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            h1 = soup.select_one("main h1, h1")
            if h1 and len(h1.get_text(strip=True)) > 2:
                title = clean(h1.get_text(" ", strip=True))
            elif soup.title and soup.title.get_text(strip=True):
                title = clean(soup.title.get_text(strip=True).split(" | ")[0].split(" - ")[0])
            else:
                title = clean(path.rsplit("/", 1)[-1].replace("-", " ").title())
            body_txt, body_html = (extract_html(html) if fetch_bodies else (None, None))
            items.append(Item(body_code="euipo", item_type="topic", title=(title or url)[:300],
                              public_url=url, creation_date=now, source_kind="html",
                              guid=url, body_txt=body_txt, body_html=body_html))
        await b.close()
    return items


def ingest_euipo_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import asyncio
    return asyncio.run(_scrape_topics_async(fetch_bodies=fetch_bodies))


def _epoch_dt(ms) -> datetime | None:
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _algolia(index: str, page: int, hits: int = 100) -> dict:
    url = (f"https://{_APP.lower()}-dsn.algolia.net/1/indexes/{index}/query"
           f"?x-algolia-api-key={_KEY}&x-algolia-application-id={_APP}")
    try:
        r = requests.post(url, json={"query": "", "page": page, "hitsPerPage": hits},
                          timeout=30)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        return {}
    return {}


def _scrape(item_type: str, *, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    index, date_field = _INDEXES[item_type]
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for page in range(max_pages):
        data = _algolia(index, page)
        rows = data.get("hits") or []
        if not rows:
            break
        for h in rows:
            slug = (h.get("fullSlug") or "").lstrip("/")
            link = h.get("link") or (norm_url(_SITE + slug) if slug else None)
            if not link or link in seen:
                continue
            seen.add(link)
            title = clean(h.get("title"))
            if not title:
                continue
            raw = h.get("body") or ""
            if isinstance(raw, list):
                raw = " ".join(str(x) for x in raw)
            elif not isinstance(raw, str):
                raw = str(raw)
            body_txt = clean(BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)[:_BODY_CAP]) or None
            body_html = clean(raw[:_BODY_CAP]) or None
            items.append(Item(
                body_code="euipo", item_type=item_type, title=title,
                public_url=link, summary=clean(h.get("summary")),
                body_txt=body_txt, body_html=body_html,
                document_date=_epoch_dt(h.get(date_field)),
                creation_date=now, source_kind="algolia", guid=link,
            ))
        if page + 1 >= int(data.get("nbPages", 0)):
            break
    return items


def ingest_euipo_news(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    return _scrape("news", fetch_bodies=fetch_bodies, max_pages=max_pages)


def ingest_euipo_events(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    return _scrape("event", fetch_bodies=fetch_bodies, max_pages=max_pages)


# --- EUIPO trade marks via TMview (bounded recent-EU slice) -----------------
# Reverse-engineering note (how this was found):
#   tmdn.org/tmview is an Angular SPA. A basic search submits
#     POST https://www.tmdn.org/tmview/api/search/results?translate=true
#   with {page,pageSize<=100,criteria:"C",basicSearch,fields:[...]}. Filter by
#   EUIPO with offices:["EM"]; sort with sortColumn:"applicationDate",desc:"true"
#   (the sort params surface only when you click the ReactTable column header).
#   basicSearch:"*" + office EM + date-desc gives the most recent EU trade marks.
#   TMview holds 20M+ global / 2.6M EUTM, so we ingest a BOUNDED recent slice.
_TMVIEW_API = "https://www.tmdn.org/tmview/api/search/results?translate=true"
_TMVIEW_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Content-Type": "application/json", "Accept": "application/json",
    "Origin": "https://www.tmdn.org", "Referer": "https://www.tmdn.org/tmview/",
}
_TM_FIELDS = ["ST13", "markImageURI", "tmName", "tmOffice", "applicationNumber",
              "applicationDate", "tradeMarkStatus", "niceClass", "applicantName", "markFeature"]


def ingest_euipo_trademarks(*, fetch_bodies: bool = True, max_pages: int = 50,
                            page_size: int = 100) -> list[Item]:
    """The most recent EU trade marks (EUIPO/EM office) from TMview, newest first."""
    import json as _json
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set[str] = set()
    for page in range(1, max_pages + 1):
        body = {"page": str(page), "pageSize": str(page_size), "criteria": "C",
                "basicSearch": "*", "offices": ["EM"],
                "sortColumn": "applicationDate", "desc": "true", "fields": _TM_FIELDS}
        try:
            r = requests.post(_TMVIEW_API, headers=_TMVIEW_HEADERS, data=_json.dumps(body), timeout=60)
            if r.status_code != 200:
                break
            rows = r.json().get("tradeMarks", [])
        except (requests.RequestException, ValueError):
            break
        if not rows:
            break
        new = 0
        for t in rows:
            st13 = t.get("ST13")
            if not st13 or st13 in seen:
                continue
            seen.add(st13)
            new += 1
            url = f"https://www.tmdn.org/tmview/#/tmview/detail/{st13}"
            appnum = t.get("applicationNumber")
            title = clean(t.get("tmName")) or (f"EUTM {appnum}" if appnum else st13)
            applicants = t.get("applicantName") or []
            if isinstance(applicants, str):
                applicants = [applicants]
            nice = t.get("niceClass") or []
            nice_s = ", ".join(str(x) for x in nice) if isinstance(nice, list) else str(nice)
            ad = t.get("applicationDate")
            doc_dt = _iso_dt(str(ad)) if ad else None
            lines = [
                f"Trade mark: {title}",
                f"Office: {t.get('tmOffice')} (EUIPO)",
                f"Application number: {appnum}" if appnum else "",
                f"Status: {t.get('tradeMarkStatus')}" if t.get("tradeMarkStatus") else "",
                f"Applicant(s): {'; '.join(applicants)}" if applicants else "",
                f"Nice class(es): {nice_s}" if nice_s else "",
                f"Type: {t.get('markFeature')}" if t.get("markFeature") else "",
            ]
            lines = [l for l in lines if l]
            body_txt = clean("\n".join(lines)) or None
            body_html = clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>")
            summary = clean(" | ".join([title, (applicants[0] if applicants else ""),
                                        t.get("tradeMarkStatus") or ""]).strip(" |"))
            items.append(Item(body_code="euipo", item_type="trademark", title=title,
                              public_url=url, summary=summary, body_txt=body_txt,
                              body_html=body_html, document_date=doc_dt, creation_date=now,
                              source_kind="tmview", guid=st13))
        if new == 0:
            break
    return items


# --- EUIPO GIView: EU geographical indications register ---------------------
# Reverse-engineering note: tmdn.org/giview is an Angular SPA (same family as
# TMview). A search POSTs to /giview/api/search/union_register with
# {databases:[...], name, pageNumber, ...}. An empty name over the two EU union
# registers returns the WHOLE EU GI register (~3,960) in one response — no
# pagination. Each record carries basicData (protectedNames, giType PDO/PGI/GI,
# productType, countries, euProtectionDate, fileNumber, status).
_GIVIEW_API = "https://www.tmdn.org/giview/api/search/union_register"
_GIVIEW_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Content-Type": "application/json", "Accept": "application/json",
    "Origin": "https://www.tmdn.org", "Referer": "https://www.tmdn.org/giview/",
}
_GIVIEW_EU_DBS = ["UNION_REGISTER_AGRI_GI", "UNION_REGISTER_CRAFT_INDUSTRIAL_GI"]
_GI_TYPE = {"PDO": "Protected Designation of Origin (PDO)",
            "PGI": "Protected Geographical Indication (PGI)",
            "GI": "Geographical Indication (GI, spirits/wines)"}


def ingest_euipo_giview(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import json as _json
    body = {"databases": _GIVIEW_EU_DBS, "name": "", "pageNumber": 1,
            "productTypes": [], "giTypes": [], "applicationTypes": [], "statuses": [],
            "agreementType": None, "agriRegisterCategories": [], "craftRegisterCategories": []}
    try:
        r = requests.post(_GIVIEW_API, headers=_GIVIEW_HEADERS, data=_json.dumps(body), timeout=90)
        if r.status_code != 200:
            return []
        recs = r.json().get("resultRecords", [])
    except (requests.RequestException, ValueError):
        return []
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    seen: set[str] = set()
    for rec in recs:
        gid = rec.get("id")
        if not gid or gid in seen:
            continue
        seen.add(gid)
        bd = rec.get("basicData") or {}
        names = bd.get("protectedNames") or []
        if isinstance(names, str):
            names = [names]
        title = clean(names[0]) if names else gid
        gi_type = bd.get("giType")
        product = bd.get("productType")
        countries = bd.get("countries") or []
        if isinstance(countries, str):
            countries = [countries]
        prot = bd.get("euProtectionDate") or bd.get("date")
        doc_dt = _iso_dt(str(prot)) if prot else None
        url = norm_url(f"https://www.tmdn.org/giview/gi/{gid}")
        lines = [
            f"Geographical indication: {title}",
            f"Other/transcribed names: {', '.join(names[1:])}" if len(names) > 1 else "",
            f"Type: {_GI_TYPE.get(gi_type, gi_type)}" if gi_type else "",
            f"Product type: {product}" if product else "",
            f"Country/ies: {', '.join(str(c) for c in countries)}" if countries else "",
            f"File number: {bd.get('fileNumber')}" if bd.get("fileNumber") else "",
            f"EU protection date: {str(prot)[:10]}" if prot else "",
            f"Status: {rec.get('status')}" if rec.get("status") else "",
            f"Register: {rec.get('database')}" if rec.get("database") else "",
        ]
        lines = [l for l in lines if l]
        items.append(Item(
            body_code="euipo", item_type="geographical_indication", title=title,
            public_url=url,
            summary=clean(" | ".join(x for x in [title, _GI_TYPE.get(gi_type, gi_type) or "",
                                                 product or "", ", ".join(str(c) for c in countries)] if x)),
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
            document_date=doc_dt, creation_date=now, source_kind="giview", guid=gid))
    return items
