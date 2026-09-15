"""What a feed item IS, for the feeds that carry more than news.

Why (measured 15 September 2026)
--------------------------------
The RSS parser stamps every entry with its feed's default type, `news`. That is true for
a newsroom feed and false for a site-wide one. Nine bodies were read from site-wide
feeds, and eu_news_items held their events, videos, podcasts, consultations,
publications, e-mail alert digests, job vacancies and procurement notices as news:

    EESC 399 rows, ~320 not news     BEREC 21, 14      ELA 16, 6       ETF 18, 8
    EFCA 25, all 25                  ERA 10, all 10    EU-LISA 30, 3   EFSA 21, 5
    EBA 43, all 43                   SRB 28, 12

The registry now reads section feeds where the body has them (EESC, BEREC), drops the
feeds that carry no news at all (ERA, EFCA, EBA: their news comes from economy_items),
and types the rest here. ONE copy of the rules, used by the sync
(dg_news_scraper.scrape_source) and by scripts/relabel_news_item_types.py, so the stock
and every future sync agree and a sync can never flip a relabelled row back.

The rules
---------
RULES[institution] is an ordered list of (regex on the URL path, outcome), first match
wins. The path has the scheme, host and a leading two-letter language segment removed.
An outcome is an item_type, SKIP (not content: vacancies, procurement notices, board
composition pages, section landing pages; the sync drops it and the stock script deletes
it) or PAGE (the URL says nothing, e.g. SRB's /en/content/<slug>: read the item's own
page and map its Drupal node type through NODE_TYPES).

A body with rules but no matching rule for a URL is UNKNOWN: the item keeps its feed
default and the caller logs it, rather than a guess being stored.
"""
from __future__ import annotations

import re
from typing import Callable, Optional, Tuple

SKIP = "skip"
PAGE = "page"
UNKNOWN = "unknown"

RULES = {
    "EESC": [
        (r"^news-media/test-r$", SKIP),
        (r"^news-media/news/", "news"),
        (r"^news-media/press-releases/", "press"),
        # president/news items arrive through the press-releases feed.
        (r"^president/news/", "press"),
        (r"^news-media/articles/", "story"),
        (r"^news-media/videos/", "video"),
        (r"^(agenda/our-events/|agenda-items/)", "event"),
        (r"^(news-media/press-summaries/|news-media/presentations/|our-work/|documents/|"
         r"newsletters/|initiatives/|node/)", "publication"),
    ],
    "BEREC": [
        (r"^news/latest-news/", "news"),
        (r"^news/press-releases/", "press"),
        (r"^(news/publications/|tasks/|berec-position-papers)", "publication"),
        (r"^events/", "event"),
        (r"^public-consultations-calls-for-inputs/", "consultation"),
        (r"^(board-of-regulators/|composition-of-the-management-board)", SKIP),
    ],
    "ELA": [
        (r"^news/", "news"),
        (r"^publications/", "publication"),
        (r"^news-event/events/", "event"),
        (r"^about-ela/procurements/", SKIP),
    ],
    "ETF": [
        (r"^publications-and-resources/publications/", "publication"),
        # Homepage announcements ("The 2026 Green Skills Award finalists are here").
        (r"^node/\d+$", "news"),
    ],
    "EULISA": [
        (r"^news-and-events/news/", "news"),
        (r"^news-and-events/videos/", "video"),
        (r"^news-and-events/events/", "event"),
    ],
    "EFSA": [
        (r"^news/", "news"),
        (r"^podcast/", "podcast"),
    ],
    "SRB": [
        # A vacancy whose page answers 403, so PAGE cannot type it.
        (r"^content/head-ict-development$", SKIP),
        (r"^content/", PAGE),
    ],
    # Feeds removed from the registry on 15 Sep 2026; the rules type their stock.
    "EFCA": [
        (r"^information-hub/video/", "video"),
        (r".", SKIP),  # vacancies, procurement and funding calls: no news in this feed
    ],
    "ERA": [
        (r".", SKIP),  # section landing pages only ("ERA Press releases", "Vacancies")
    ],
    "EBA": [
        (r"^publications-and-media/events/", "event"),
        (r"^node/\d+$", "publication"),  # "EBA E-mail alert <date>" digests
    ],
}

# Drupal node types, read from the item's own page for PAGE rules.
NODE_TYPES = {
    "srb-news": "news",
    "srb-event": "event",
    "srb-tender": SKIP,
    "srb-vacancy": SKIP,
    "news": "news",
    "event": "event",
    "video": "video",
    "procurement": SKIP,
    "simplenews-issue": "publication",
}

_LANG = re.compile(r"^https?://[^/]+/(?:[a-z]{2}/)?")
_NODE_TYPE = re.compile(r"(?:page-node-type-|node--type-)([a-z0-9_-]+)")


def url_path(url: str) -> str:
    return _LANG.sub("", (url or "").strip()).split("?")[0].split("#")[0].rstrip("/")


def has_rules(institution: Optional[str]) -> bool:
    return (institution or "").upper() in RULES


def rule_for(institution: str, url: str) -> str:
    """The rule outcome for a URL: an item_type, SKIP, PAGE or UNKNOWN."""
    path = url_path(url)
    for pattern, outcome in RULES.get((institution or "").upper(), []):
        if re.search(pattern, path):
            return outcome
    return UNKNOWN


def type_from_page(html: str) -> str:
    """The item_type a page declares through its Drupal node type, or UNKNOWN."""
    for node_type in _NODE_TYPE.findall(html or ""):
        if node_type in NODE_TYPES:
            return NODE_TYPES[node_type]
    return UNKNOWN


def item_type_for(institution: str, url: str,
                  fetch: Optional[Callable[[str], Optional[str]]] = None) -> Tuple[str, str]:
    """(outcome, how) for one item. outcome is an item_type, SKIP or UNKNOWN; `how` says
    which evidence decided it ("url", "page", "page-unreadable", "no-rule")."""
    outcome = rule_for(institution, url)
    if outcome == UNKNOWN:
        return UNKNOWN, "no-rule"
    if outcome != PAGE:
        return outcome, "url"
    html = fetch(url) if fetch else None
    if not html:
        return UNKNOWN, "page-unreadable"
    found = type_from_page(html)
    return found, ("page" if found != UNKNOWN else "page-no-node-type")
