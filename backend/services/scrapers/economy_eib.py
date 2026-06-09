"""
EIB — European Investment Bank, with EIF embedded (api_econ.md L567-650).
/api/v2/eu-financial-institutions/eib.

The EIB site (eib.org) renders its press, publications and events listings from
a single JSON search backend that ALSO covers the European Investment Fund
(eif.org) — so EIF content is folded in here per the agreed scope (no separate
EIF folder). Source map (verified):

  POST https://www.eib.org/provider-search/search/v2
    body: websites=["EIF","EIB"], searchRequestParam.websiteFullTypes=[...],
          languageRequestParam.language="EN",
          pageableRequestParam.{pageNumber, itemPerPage}
    -> items[] with url (relative) + websiteUrl (eib.org or eif.org), title,
       description, type/subType, startDate (epoch ms).

  news         : websiteFullTypes = eib-press-new, eib-press-release, eif-press-release
  publications : websiteFullTypes = eib-publication, eif-publication
  events       : websiteFullTypes = eib-event

Each item's detail page (websiteUrl + url) is fetched for the body. No LLM.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean, norm_url, fetch_detail

_API = "https://www.eib.org/provider-search/search/v2"
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 BrubruBot/1.0"
_TIMEOUT = 45

NEWS_TYPES = ["eib-press-new", "eib-press-release", "eif-press-release"]
PUB_TYPES = ["eib-publication", "eif-publication"]
EVENT_TYPES = ["eib-event"]


def _epoch_dt(ms) -> datetime | None:
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _search(types, page: int, *, item_per_page: int = 20, tries: int = 3) -> list[dict]:
    payload = {
        "websites": ["EIF", "EIB"],
        "searchRequestParam": {
            "search": "", "websiteFullTypes": types,
            "orTags": True, "orCountries": True, "orRegions": True, "orSubjects": True,
        },
        "languageRequestParam": {"language": "EN"},
        "pageableRequestParam": {"pageable": True, "pageNumber": page, "itemPerPage": item_per_page},
    }
    for attempt in range(tries):
        try:
            r = requests.post(_API, headers={"User-Agent": _UA, "Content-Type": "application/json"},
                              data=json.dumps(payload), timeout=_TIMEOUT)
            if r.status_code == 200:
                return r.json().get("items", []) or []
        except requests.RequestException:
            pass
        time.sleep(3.0 * (attempt + 1))
    return []


def _collect(item_type: str, types, *, fetch_bodies: bool, max_pages: int) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for page in range(max_pages):
        rows = _search(types, page)
        if not rows:
            break
        new = 0
        for it in rows:
            rel = it.get("url") or ""
            base = it.get("websiteUrl") or "https://www.eib.org"
            url = norm_url(base + rel) if rel.startswith("/") else norm_url(rel or base)
            if not url or url in seen:
                continue
            seen.add(url)
            new += 1
            items.append(Item(
                body_code="eib", item_type=item_type,
                title=clean(it.get("title")) or url,
                public_url=url, summary=clean(it.get("description")),
                document_date=_epoch_dt(it.get("startDate")),
                creation_date=now, source_kind="html", guid=url,
            ))
        if new == 0:
            break
        time.sleep(1.5)
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_eib_news(*, fetch_bodies: bool = True, max_pages: int = 10) -> list[Item]:
    return _collect("news", NEWS_TYPES, fetch_bodies=fetch_bodies, max_pages=max_pages)


def ingest_eib_publications(*, fetch_bodies: bool = True, max_pages: int = 10) -> list[Item]:
    return _collect("publication", PUB_TYPES, fetch_bodies=fetch_bodies, max_pages=max_pages)


def ingest_eib_events(*, fetch_bodies: bool = True, max_pages: int = 8) -> list[Item]:
    return _collect("event", EVENT_TYPES, fetch_bodies=fetch_bodies, max_pages=max_pages)
