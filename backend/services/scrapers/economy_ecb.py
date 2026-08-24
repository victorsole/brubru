"""
ECB + ECB Banking Supervision (SSM) ingestion for the /api/v2/ecb folder.

Verified source map (URL-verification pass, api_econ.md L70-279):
  - news         : RSS feeds (/rss/press.html, /rss/blog.html | SSM /rss/press.xml,
                   /rss/speeches.xml) -> item detail pages are SERVER-RENDERED HTML.
  - publications : ECB RSS (/rss/pub.html, /rss/wppub.html, /rss/statpress.html)
                   -> HTML or PDF; SSM publications listing is JS-rendered (Playwright).
  - events       : conferences listing is JS-rendered (Playwright) -> dated <dl> rows.
  - legal        : no RSS -> Cellar SPARQL (ECB as author), the canonical EU source.

Shared primitives live in economy_common. No LLM is used anywhere.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import feedparser
import requests
from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, _UA, clean, norm_url, http_get, to_dt, fetch_detail, parse_listing_date,
)

# --- feed map --------------------------------------------------------------
ECB_FEEDS = {
    "news": [
        "https://www.ecb.europa.eu/rss/press.html",
        "https://www.ecb.europa.eu/rss/blog.html",
    ],
    "publication": [
        "https://www.ecb.europa.eu/rss/pub.html",
        "https://www.ecb.europa.eu/rss/wppub.html",
        "https://www.ecb.europa.eu/rss/statpress.html",
    ],
}
SSM_FEEDS = {
    "news": [
        "https://www.bankingsupervision.europa.eu/rss/press.xml",
        "https://www.bankingsupervision.europa.eu/rss/speeches.xml",
    ],
}

# JS-rendered listing pages (date-indexed <dl> injected client-side -> Playwright).
ECB_EVENT_PAGES = ["https://www.ecb.europa.eu/press/conferences/html/index.en.html"]
SSM_EVENT_PAGES = ["https://www.bankingsupervision.europa.eu/press/conferences/html/index.en.html"]
SSM_PUB_PAGES = ["https://www.bankingsupervision.europa.eu/press/other-publications/publications/html/index.en.html"]

_CELLAR_SPARQL = "http://publications.europa.eu/webapi/rdf/sparql"
_ECB_AUTHORITY = "http://publications.europa.eu/resource/authority/corporate-body/ECB"


# --- feed-driven ingestion (news, publications) ----------------------------
def _feed_entries(feed_url: str):
    r = http_get(feed_url)
    if r is None:
        return []
    return feedparser.parse(r.content).entries or []


def ingest_feeds(body_code: str, item_type: str, feed_urls: Iterable[str],
                 *, fetch_bodies: bool = True, limit_per_feed: int | None = None) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for feed_url in feed_urls:
        entries = _feed_entries(feed_url)
        if limit_per_feed:
            entries = entries[:limit_per_feed]
        for e in entries:
            link = norm_url(getattr(e, "link", "") or "")
            if not link or link in seen:
                continue
            seen.add(link)
            title = clean((getattr(e, "title", "") or "").strip()) or link
            summary = clean((getattr(e, "summary", "") or "").strip()) or None
            doc_dt = to_dt(getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None))
            it = Item(body_code=body_code, item_type=item_type, title=title, public_url=link,
                      summary=summary, document_date=doc_dt, creation_date=now,
                      guid=(getattr(e, "id", None) or link), source_kind="rss")
            if fetch_bodies:
                it.body_txt, it.body_html, it.source_kind = fetch_detail(link)
            items.append(it)
    return items


def ingest_ecb_news(**kw) -> list[Item]:
    return ingest_feeds("ecb", "news", ECB_FEEDS["news"], **kw)


def ingest_ecb_publications(**kw) -> list[Item]:
    return ingest_feeds("ecb", "publication", ECB_FEEDS["publication"], **kw)


def ingest_ssm_news(**kw) -> list[Item]:
    return ingest_feeds("ecb_ssm", "news", SSM_FEEDS["news"], **kw)


# --- rendered listings (events, SSM publications) --------------------------
def scrape_rendered_listing(body_code: str, item_type: str, pages: Iterable[str],
                            *, fetch_bodies: bool = True, settle_ms: int = 6000) -> list[Item]:
    """Render a JS date-indexed list with Playwright and parse <dt>/<dd> rows."""
    from services.scrapers.waf_browser_fetcher import WafBrowserFetcher

    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    with WafBrowserFetcher(settle_ms=settle_ms) as fetcher:
        for page in pages:
            res = fetcher.fetch(page, strip_chrome=False)
            if not res.html:
                continue
            soup = BeautifulSoup(res.html, "html.parser")
            import re as _re
            base = _re.match(r"^(https?://[^/]+)", page).group(1)
            for dd in soup.find_all("dd"):
                a = dd.find("a", href=True)
                if not a:
                    continue
                href = a["href"]
                url = norm_url(href if href.startswith("http") else base + href)
                if url in seen or "/shared/" in url:
                    continue
                title = clean(a.get_text(" ", strip=True))
                if not title:
                    continue
                seen.add(url)
                dt_node = dd.find_previous_sibling("dt")
                doc_dt = parse_listing_date(dt_node.get_text(" ", strip=True)) if dt_node else None
                items.append(Item(body_code=body_code, item_type=item_type, title=title,
                                  public_url=url, document_date=doc_dt, creation_date=now,
                                  source_kind="html", guid=url))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_ecb_events(**kw) -> list[Item]:
    return scrape_rendered_listing("ecb", "event", ECB_EVENT_PAGES, **kw)


def ingest_ssm_events(**kw) -> list[Item]:
    return scrape_rendered_listing("ecb_ssm", "event", SSM_EVENT_PAGES, **kw)


def ingest_ssm_publications(**kw) -> list[Item]:
    return scrape_rendered_listing("ecb_ssm", "publication", SSM_PUB_PAGES, **kw)


# --- legal acts (Cellar SPARQL) --------------------------------------------
def fetch_ecb_legal_acts(limit: int = 100, **_) -> list[Item]:
    """ECB legal acts via Cellar SPARQL (author = ECB corporate body). CELEX verbatim."""
    query = f"""
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT DISTINCT ?celex ?title ?date WHERE {{
  ?work cdm:work_created_by_agent <{_ECB_AUTHORITY}> .
  ?work cdm:resource_legal_id_celex ?celex .
  OPTIONAL {{ ?work cdm:work_date_document ?date . }}
  ?exp cdm:expression_belongs_to_work ?work .
  ?exp cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> .
  ?exp cdm:expression_title ?title .
}}
ORDER BY DESC(?date)
LIMIT {int(limit)}
"""
    try:
        r = requests.get(_CELLAR_SPARQL,
                         params={"query": query, "format": "application/sparql-results+json"},
                         headers={"User-Agent": _UA, "Accept": "application/sparql-results+json"},
                         timeout=60)
        if r.status_code != 200:
            return []
        rows = r.json().get("results", {}).get("bindings", [])
    except (requests.RequestException, ValueError):
        return []

    now = datetime.now(timezone.utc)
    items: list[Item] = []
    for b in rows:
        celex = b.get("celex", {}).get("value")
        title = clean((b.get("title", {}).get("value") or "").strip())
        if not celex or not title:
            continue
        date_raw = b.get("date", {}).get("value")
        doc_dt = None
        if date_raw:
            try:
                doc_dt = datetime.fromisoformat(date_raw[:10]).replace(tzinfo=timezone.utc)
            except ValueError:
                doc_dt = None
        url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
        items.append(Item(body_code="ecb", item_type="legal", title=title, public_url=url,
                          summary=f"ECB legal act — CELEX {celex}",
                          body_html=f'<p>{title}</p><p>CELEX <a href="{url}">{celex}</a></p>',
                          body_txt=f"{title}\nCELEX {celex}", document_date=doc_dt,
                          creation_date=now, source_kind="cellar", guid=celex,
                          extras={"celex": celex}))
    return items


# --- ECB Data Portal: catalogue of statistical datasets (dataflows) ---------
# The ECB Data Portal is a statistical/time-series database (millions of series),
# which does NOT fit the row-per-item model. The honest representation is a
# CATALOGUE: one item per SDMX dataflow (dataset), pointing to where the data
# lives + how to query it. The dataflow list comes from the SDMX structure API
# (returns SDMX-ML XML; the JSON variants 406 here).
def ingest_ecb_datasets(*, fetch_bodies: bool = True, **_):
    from xml.etree import ElementTree as ET
    from datetime import datetime, timezone
    from services.scrapers.economy_common import Item, clean
    url = "https://data-api.ecb.europa.eu/service/dataflow/ECB"
    r = http_get(url)
    if r is None:
        return []
    try:
        root = ET.fromstring(r.text)
    except ET.ParseError:
        return []
    ns = {"s": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure",
          "c": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common"}
    now = datetime.now(timezone.utc)
    items = []
    seen = set()
    for df in root.findall(".//s:Dataflow", ns):
        did = df.get("id")
        if not did or did in seen:
            continue
        seen.add(did)
        nm = df.find("c:Name", ns)
        name = clean(nm.text) if nm is not None and nm.text else did
        desc = df.find("c:Description", ns)
        portal = f"https://data.ecb.europa.eu/data/datasets/{did}"
        struct = f"https://data-api.ecb.europa.eu/service/datastructure/ECB/{did}"
        data_api = f"https://data-api.ecb.europa.eu/service/data/{did}"
        lines = [
            f"Dataset: {name}",
            f"Dataflow code: {did}",
            f"Description: {clean(desc.text)}" if (desc is not None and desc.text) else "",
            f"Browse: {portal}",
            f"Data (SDMX): {data_api}/<series key>?format=csvdata",
            f"Structure (SDMX): {struct}",
        ]
        lines = [l for l in lines if l]
        body_txt = clean("\n".join(lines))
        body_html = clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>")
        items.append(Item(body_code="ecb", item_type="dataset", title=name,
                          public_url=portal, summary=clean(f"ECB statistical dataset {did} — {name}"),
                          body_txt=body_txt, body_html=body_html,
                          document_date=None, creation_date=now,
                          source_kind="sdmx-catalogue", guid=did))
    return items
