"""
EESC — European Economic and Social Committee (api_eesc_cor_ombud.md). /api/v2/eesc.

The EESC site (eesc.europa.eu) is a Drupal build, server-rendered and reachable with
plain requests. Source map (verified 25 Jun 2026):
  - news          : /en/news-media/news        — .group-details rows (title link +
                    <time datetime>). Same layout for press releases and events.
  - press_release : /en/news-media/press-releases
  - event         : /en/agenda/our-events/events
  - opinion       : /en/our-work/opinions-information-reports/opinions — links to
                    /opinions/<slug> (the EESC's adopted opinions and reports).
  - topic         : about, members-groups, sections, observatories and the policy-area
                    pages.

The EESC is the EU's consultative body representing employers, workers and civil
society; its opinions feed into EU legislation. Reads from economy_items (body row
seeded by migration 169); 5 mandatory datapoints. Scope: read:economy. No LLM.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, _iso_dt, snapshot_topics,
)

_BASE = "https://www.eesc.europa.eu"

NEWS_PAGE = f"{_BASE}/en/news-media/news"
PRESS_PAGE = f"{_BASE}/en/news-media/press-releases"
EVENTS_PAGE = f"{_BASE}/en/agenda/our-events/events"
OPINIONS_PAGE = f"{_BASE}/en/our-work/opinions-information-reports/opinions"

_POLICY = [
    "agriculture-rural-development-fisheries", "climate-change",
    "cohesion-regional-and-urban-policy", "consumers",
    "digital-change-and-information-society", "economic-and-monetary-union",
    "education-and-training", "employment", "energy", "enterprise", "environment",
    "external-relations-and-international-trade", "financial-services-and-capital-markets",
    "fundamental-and-citizens-rights", "housing", "industry-and-industrial-change",
    "institutional-affairs-and-eu-budget", "migration-and-asylum",
    "research-and-innovation", "services-general-interest", "single-market",
    "social-affairs", "sustainable-development", "taxation", "transport",
]
_SECTIONS = [
    "economic-and-monetary-union-and-economic-and-social-cohesion-eco",
    "single-market-production-and-consumption-int",
    "transport-energy-infrastructure-and-information-society-ten",
    "employment-social-affairs-and-citizenship-soc",
    "agriculture-rural-development-and-environment-nat",
    "external-relations-section-rex",
    "consultative-commission-industrial-change-ccmi",
]
_TOPIC_PATHS = [
    "/en/about",
    "/en/president/role",
    "/en/members-groups",
    "/en/members-groups/groups/employers-group",
    "/en/members-groups/groups/workers-group",
    "/en/members-groups/groups/civil-society-organisations-group",
    "/en/sections-other-bodies",
    "/en/sections-other-bodies/observatories/single-market-observatory",
    "/en/sections-other-bodies/observatories/labour-market-observatory",
    "/en/sections-other-bodies/observatories/sustainable-development-observatory",
    "/en/our-work",
] + [f"/en/sections-other-bodies/sections-commission/{s}" for s in _SECTIONS] \
  + [f"/en/policies/policy-areas/{p}" for p in _POLICY]


def _parse_group_details(html: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for gd in soup.select(".group-details"):
        a = gd.select_one("h2 a[href], h3 a[href], .field--name-title a[href], a[href]")
        if not a or not a.get("href"):
            continue
        title = clean(a.get_text(" ", strip=True))
        if not title or len(title) < 8:
            continue
        t = gd.select_one("time[datetime]")
        doc_dt = _iso_dt(t["datetime"]) if t and t.get("datetime") else None
        out.append((norm_url(a["href"] if a["href"].startswith("http") else _BASE + a["href"]),
                    title, doc_dt))
    return out


def _scrape_listing(url: str, item_type: str, *, fetch_bodies: bool) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(url)
    if r is None:
        return items
    for purl, title, doc_dt in _parse_group_details(r.text):
        if purl in seen:
            continue
        seen.add(purl)
        items.append(Item(body_code="eesc", item_type=item_type, title=title[:300],
                          public_url=purl, document_date=doc_dt, creation_date=now,
                          source_kind="html", guid=purl))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_eesc_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape_listing(NEWS_PAGE, "news", fetch_bodies=fetch_bodies)


def ingest_eesc_press_releases(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape_listing(PRESS_PAGE, "press_release", fetch_bodies=fetch_bodies)


def ingest_eesc_events(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape_listing(EVENTS_PAGE, "event", fetch_bodies=fetch_bodies)


def ingest_eesc_opinions(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(OPINIONS_PAGE)
    if r is None:
        return items
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if not re.search(r"/opinions/[a-z0-9-]{6,}", href):
            continue
        title = clean(a.get_text(" ", strip=True))
        if not title or len(title) < 10:
            continue
        url = norm_url(href if href.startswith("http") else _BASE + href)
        if url in seen:
            continue
        seen.add(url)
        items.append(Item(body_code="eesc", item_type="opinion", title=title[:300],
                          public_url=url, creation_date=now, source_kind="html", guid=url))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
    return items


def ingest_eesc_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("eesc", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
