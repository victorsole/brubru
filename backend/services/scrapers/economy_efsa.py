"""
EFSA — European Food Safety Authority (api_health.md). /api/v2/efsa.

EFSA runs a Drupal site (efsa.europa.eu). Source map (verified):
  - news         : /en/press/rss — the press RSS feed (clean, dated) -> detail HTML.
                   (The /en/news page mixes in multimedia and paginates via JS.)
  - publications : /en/publications — article cards with a heading link and a
                   <time datetime>. Many entries are EFSA Journal outputs hosted on
                   Wiley (external DOI); the 5 datapoints + title + date are always
                   present, body_txt only when the target is fetchable.

EFSA has no separate events feed, so news + publications. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, _iso_dt, snapshot_topics,
)
from services.scrapers.economy_ecb import ingest_feeds

_BASE = "https://www.efsa.europa.eu"
EFSA_NEWS_FEEDS = [f"{_BASE}/en/press/rss"]

# Curated about + thematic topic landing pages, snapshotted as topics. The
# harvested /en/topics/topic/* set plus core EFSA topics on the same URL pattern
# (snapshot_topics drops any that 404).
_TOPIC_PATHS = [
    "/en/about/about-efsa",
    "/en/topics/genetically-modified-organisms",
    "/en/topics/topic/animal-health",
    "/en/topics/topic/animal-welfare",
    "/en/topics/topic/antimicrobial-resistance",
    "/en/topics/topic/biological-hazards",
    "/en/topics/topic/chemical-contaminants-food-feed",
    "/en/topics/topic/emerging-risks",
    "/en/topics/topic/feed-additives",
    "/en/topics/topic/food-additives",
    "/en/topics/topic/food-contact-materials",
    "/en/topics/topic/food-ingredients",
    "/en/topics/topic/novel-food",
    "/en/topics/topic/nutrition",
    "/en/topics/topic/pesticides",
    "/en/topics/topic/plant-health",
]


def ingest_efsa_news(**kw) -> list[Item]:
    return ingest_feeds("efsa", "news", EFSA_NEWS_FEEDS, **kw)


def ingest_efsa_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("efsa", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)


def _parse_pubs(html: str):
    main = BeautifulSoup(html, "html.parser").select_one("main") or BeautifulSoup(html, "html.parser")
    out = []
    for a_art in main.select("article"):
        a = a_art.select_one("h2 a[href], h3 a[href]") or a_art.find("a", href=True)
        t = a_art.select_one("time[datetime]")
        if not a or not a.get("href") or not t:
            continue
        href = a["href"]
        url = norm_url(href if href.startswith("http") else _BASE + href)
        title = clean(a.get_text(" ", strip=True))
        if not title:
            continue
        out.append((url, title, _iso_dt(t.get("datetime"))))
    return out


def ingest_efsa_publications(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    listing = f"{_BASE}/en/publications"
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for page in range(max_pages):
        url = listing if page == 0 else f"{listing}?page={page}"
        r = http_get(url)
        if r is None:
            break
        rows = _parse_pubs(r.text)
        new = 0
        for u, title, doc_dt in rows:
            if u in seen:
                continue
            seen.add(u)
            new += 1
            items.append(Item(body_code="efsa", item_type="publication", title=title,
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


# --- EFSA scientific databases (Zenodo .xlsx) -------------------------------
# EFSA publishes its databases as Zenodo datasets. The clean entity tables are
# ingested row-per-record via the shared xlsx ingestor (sheet-aware; rows get a
# synthesised public_url from the dataset page so the UNIQUE constraint holds).
EFSA_DATASETS = [
    {"item_type": "openfoodtox_substance", "slug": "openfoodtox", "noun": "OpenFoodTox substances",
     "xlsx": "https://zenodo.org/api/records/19388272/files/OFT3.0%20export%20repository.xlsx/content",
     "sheet": "REF_SUB",
     "title_cols": ["IupacName", "ChemicalName", "Description"], "url_cols": [], "date_cols": [],
     "record_url": "https://www.efsa.europa.eu/en/data-report/chemical-hazards-database-openfoodtox",
     "extra": "OpenFoodTox 3.0 — EFSA's chemical hazards database: substances with CAS number, IUPAC name and regulatory references."},
    {"item_type": "xylella_host", "slug": "xylella-host-plants", "noun": "Xylella host-plant records",
     "xlsx": "https://zenodo.org/api/records/18195508/files/Xylella%20spp%20host%20plant%20database_VERSION%2013.xlsx/content",
     "sheet": "observation",
     "title_cols": ["PlantSpecies", "PlantGenus", "PlantName", "Plant"], "url_cols": [], "date_cols": [],
     "record_url": "https://www.efsa.europa.eu/en/data-report/xylella-spp-host-plant-database",
     "extra": "Host plants of Xylella fastidiosa — one record per observation (plant taxon, Xylella species/subspecies, reference, infection type)."},
]


def make_efsa_dataset_ingestor(cfg):
    from services.scrapers.economy_common import ingest_xlsx_dataset

    def _ingest(*, fetch_bodies: bool = True, **_):
        return ingest_xlsx_dataset(cfg["xlsx"], "efsa", cfg["item_type"],
                                   title_cols=cfg["title_cols"], url_cols=cfg["url_cols"],
                                   date_cols=cfg["date_cols"], sheet=cfg.get("sheet"),
                                   record_url=cfg["record_url"])
    _ingest.__name__ = f"ingest_efsa_{cfg['item_type']}"
    return _ingest


EFSA_DATASET_INGESTORS = {cfg["item_type"]: make_efsa_dataset_ingestor(cfg) for cfg in EFSA_DATASETS}
