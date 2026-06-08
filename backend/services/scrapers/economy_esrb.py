"""
ESRB — European Systemic Risk Board (/api/v2/eu-financial-institutions/esrb).

ESRB runs on the ECB CMS (api_econ.md L472-505). Source map:
  - news         : /rss/press.xml (press releases + speeches, dated) -> detail HTML.
  - publications : the macroprudential-policy (mppa) pages — recommendations,
                   warnings, opinions, stress tests, responses — are server-rendered
                   date-indexed <dl> lists (no Playwright).
  - events       : /news/schedule — server-rendered <dl>.

The /news/pr and /pub index pages inject their <dl> client-side, so news comes
from the RSS feed instead. No LLM is used.
"""
from __future__ import annotations

from services.scrapers.economy_common import scrape_dl_listing, Item
from services.scrapers.economy_ecb import ingest_feeds

_BASE = "https://www.esrb.europa.eu"

ESRB_NEWS_FEEDS = [f"{_BASE}/rss/press.xml"]
ESRB_PUB_PAGES = [
    f"{_BASE}/mppa/recommendations/html/index.en.html",
    f"{_BASE}/mppa/warnings/html/index.en.html",
    f"{_BASE}/mppa/opinions/html/index.en.html",
    f"{_BASE}/mppa/stress/html/index.en.html",
    f"{_BASE}/mppa/responses/html/index.en.html",
]
ESRB_EVENT_PAGES = [f"{_BASE}/news/schedule/html/index.en.html"]


def ingest_esrb_news(**kw) -> list[Item]:
    return ingest_feeds("esrb", "news", ESRB_NEWS_FEEDS, **kw)


def ingest_esrb_publications(**kw) -> list[Item]:
    return scrape_dl_listing("esrb", "publication", ESRB_PUB_PAGES, _BASE, use_playwright=False, **kw)


def ingest_esrb_events(**kw) -> list[Item]:
    return scrape_dl_listing("esrb", "event", ESRB_EVENT_PAGES, _BASE, use_playwright=False, **kw)
