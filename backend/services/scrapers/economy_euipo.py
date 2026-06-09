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

from services.scrapers.economy_common import Item, clean, norm_url, _BODY_CAP, _iso_dt

_APP = "ZYN8P9OCP2"
_KEY = "428a6eab6ad825546f741c199084e245"  # public search-only key shipped by the EUIPO site
_SITE = "https://www.euipo.europa.eu/"
_INDEXES = {"news": ("ews-en-news", "date"), "event": ("ews-en-events", "startDate")}


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
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
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
