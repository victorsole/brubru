"""
EPPO — European Public Prosecutor's Office (api_econ.md L693-710).
/api/v2/eu-financial-institutions/eppo.

EPPO runs on the EU ECL stack (eppo.europa.eu). Source map (verified):
  - news         : /en/media/news — ECL .ecl-content-item cards with <time
                   datetime>; ?page=N paginated. Detail = HTML.
  - publications : /en/documents/documents — ECL .ecl-file cards (title + date +
                   PDF link); ?page=N paginated. Bodies extracted from the PDFs.

EPPO publishes no events/agendas feed, so only news + publications are exposed.
No LLM is used.
"""
from __future__ import annotations

from services.scrapers.economy_common import (
    Item, scrape_ecl_listing, scrape_ecl_file_listing,
)

_BASE = "https://www.eppo.europa.eu"

EPPO_NEWS_PAGES = [f"{_BASE}/en/media/news"]
EPPO_PUB_PAGES = [f"{_BASE}/en/documents/documents"]


def ingest_eppo_news(**kw) -> list[Item]:
    return scrape_ecl_listing("eppo", "news", EPPO_NEWS_PAGES, _BASE, **kw)


def ingest_eppo_publications(**kw) -> list[Item]:
    return scrape_ecl_file_listing("eppo", "publication", EPPO_PUB_PAGES, _BASE, **kw)
