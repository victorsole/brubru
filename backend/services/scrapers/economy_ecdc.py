"""
ECDC — European Centre for Disease Prevention and Control (api_health.md).
/api/v2/ecdc.

ECDC runs a Drupal site (ecdc.europa.eu) whose listings are server-rendered by
its Search API view. The category-filtered search endpoint is the canonical
paginated feed. Source map (verified):
  - news         : /en/search?...&f[0]=categories:1307 — article.ct-news cards
                   (heading link + <time datetime>); ?page=N paginated. Detail = HTML.
  - publications : /en/search?...&f[0]=categories:1244 — article.ct-publication cards.

ECDC has no separate events feed (news + events share the news-events space), so
news + publications. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, _iso_dt, extract_html,
)

_BASE = "https://www.ecdc.europa.eu"
_SEARCH = _BASE + "/en/search?s=&sort_bef_combine=date_DESC&f%5B0%5D=categories%3A"

# Curated about / tools / data-portal landing pages (stable reference content,
# distinct from the time-sensitive outbreak pages), snapshotted as topics.
_TOPIC_PATHS = [
    "/en/about-us",
    "/en/about-us/ecdcs-organisational-structure",
    "/en/about-us/ecdcs-governance",
    "/en/about-us/what-we-do",
    "/en/about-us/ecdcs-partnerships-and-networks",
    "/en/about-ecdc/partners-and-networks/disease-and-laboratory-networks",
    "/en/about-us/what-we-do/country-support",
    "/en/data-tools",
    "/en/epiet-euphem",
    "/en/training",
    "/en/tools/outbreak-surveillance-tools",
    "/en/tools/country-resources",
    "/en/publications-data/epipulse-european-surveillance-portal-infectious-diseases",
    "/en/publications-data/ecdc-geoportal",
    "/en/publications-data/european-respiratory-diseases-forecasting-hub-respicast",
    "/en/publications-data/learning-portal",
]


def ingest_ecdc_topics(*, fetch_bodies: bool = True) -> list[Item]:
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    for path in _TOPIC_PATHS:
        url = _BASE + path
        r = http_get(url)
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.select_one("main h1, h1")
        if h1 and len(h1.get_text(strip=True)) > 2:
            title = clean(h1.get_text(" ", strip=True))
        elif soup.title and soup.title.get_text(strip=True):
            title = clean(soup.title.get_text(strip=True).split(" | ")[0].split(" - ")[0])
        else:
            title = path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
        body_txt, body_html = (extract_html(r.text) if fetch_bodies else (None, None))
        items.append(Item(body_code="ecdc", item_type="topic", title=title[:300],
                          public_url=url, creation_date=now, source_kind="html",
                          guid=url, body_txt=body_txt, body_html=body_html))
    return items
_SOURCES = {
    "news": (f"{_SEARCH}1307", "article.ct-news"),
    "publication": (f"{_SEARCH}1244", "article.ct-publication"),
}


def _parse(html: str, node_sel: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for node in soup.select(node_sel):
        a = node.select_one("h2 a[href], h3 a[href]") or node.find("a", href=True)
        if not a or not a.get("href"):
            continue
        url = norm_url(a["href"] if a["href"].startswith("http") else _BASE + a["href"])
        title = clean(a.get_text(" ", strip=True))
        if not title:
            continue
        t = node.select_one("time[datetime]")
        out.append((url, title, _iso_dt(t.get("datetime")) if t else None))
    return out


def _scrape(item_type: str, *, fetch_bodies: bool, max_pages: int) -> list[Item]:
    listing, node_sel = _SOURCES[item_type]
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for page in range(max_pages):
        url = listing if page == 0 else f"{listing}&page={page}"
        r = http_get(url)
        if r is None:
            break
        rows = _parse(r.text, node_sel)
        new = 0
        for u, title, doc_dt in rows:
            if u in seen:
                continue
            seen.add(u)
            new += 1
            items.append(Item(body_code="ecdc", item_type=item_type, title=title,
                              public_url=u, document_date=doc_dt, creation_date=now,
                              source_kind="html", guid=u))
        if new == 0:
            break
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_ecdc_news(*, fetch_bodies: bool = True, max_pages: int = 4) -> list[Item]:
    return _scrape("news", fetch_bodies=fetch_bodies, max_pages=max_pages)


def ingest_ecdc_publications(*, fetch_bodies: bool = True, max_pages: int = 4) -> list[Item]:
    return _scrape("publication", fetch_bodies=fetch_bodies, max_pages=max_pages)


# --- ECDC Surveillance Atlas: catalogue of surveilled diseases --------------
# The Surveillance Atlas of Infectious Diseases is statistical (case counts by
# country/period), so the honest shape is a CATALOGUE: one item per disease
# (health topic) ECDC monitors, with the Atlas link + REST API for the figures.
# API found by capturing the Atlas SPA's XHRs: atlas.ecdc.europa.eu/public/AtlasService/rest.
def ingest_ecdc_surveillance(*, fetch_bodies: bool = True, **_):
    import requests
    from datetime import datetime, timezone
    from services.scrapers.economy_common import Item, clean
    B = "https://atlas.ecdc.europa.eu/public/AtlasService/rest"
    H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", "Accept": "application/json"}
    topics: dict = {}
    for did in (27, 1):
        try:
            r = requests.get(f"{B}/GetHealthTopicsForDataset?datasetId={did}", headers=H, timeout=30)
            if r.status_code == 200:
                for t in (r.json().get("HealthTopics") or []):
                    code = t.get("Code")
                    if code:
                        topics.setdefault(code, t.get("Label") or code)
        except requests.RequestException:
            continue
    now = datetime.now(timezone.utc)
    items = []
    for code, label in topics.items():
        url = f"https://atlas.ecdc.europa.eu/public/index.aspx?Dataset=27&HealthTopic={code}"
        lines = [
            f"Disease / health topic: {label}",
            f"Surveillance code: {code}",
            f"Surveillance Atlas: {url}",
            f"Data (REST): {B}/GetDatasets and /GetHealthTopicsForDataset?datasetId=27",
        ]
        body_txt = clean("\n".join(lines))
        body_html = clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>")
        items.append(Item(body_code="ecdc", item_type="surveillance_topic", title=clean(label),
                          public_url=url, summary=clean(f"ECDC surveillance: {label} ({code})"),
                          body_txt=body_txt, body_html=body_html, document_date=None,
                          creation_date=now, source_kind="atlas-catalogue", guid=code))
    return items
