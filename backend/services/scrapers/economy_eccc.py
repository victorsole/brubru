"""
ECCC — European Cybersecurity Competence Centre (api_market.md L535-550).
/api/v2/eccc.

cybersecurity-centre.europa.eu runs on the EU ECL stack, server-rendered, plain
requests. Source map (verified 25 Jun 2026):
  - news            : /news_en — ECL .ecl-content-item listing.
  - call            : /funding-opportunities/calls-proposals_en +
                      /funding-opportunities/call-expressions-interest_en — ECL listing.
  - governing_board : /governing-board_en — the Governing Board membership table
                      (country, name, role, Member/Alternate) with a member-document
                      link per row. Fetched in full per the harvest note.
  - ncc             : /nccs-0_en — the list of confirmed National Coordination
                      Centres (country + designated organisation). Fetched in full.
  - topic           : about + strategic-agenda + funding-opportunities pages.

The ECCC manages the EU's cybersecurity funding (Digital Europe, Horizon Europe
cyber) and coordinates the National Coordination Centres. Reads from economy_items
(body row seeded by migration 174); 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, scrape_ecl_listing, snapshot_topics,
)

_BASE = "https://cybersecurity-centre.europa.eu"

NEWS_PAGES = [f"{_BASE}/news_en"]
CALL_PAGES = [f"{_BASE}/funding-opportunities/calls-proposals_en",
              f"{_BASE}/funding-opportunities/call-expressions-interest_en"]
GB_PAGE = f"{_BASE}/governing-board_en"
NCC_PAGE = f"{_BASE}/nccs-0_en"

_TOPIC_PATHS = [
    "/about-us_en",
    "/strategic-agenda_en",
    "/funding-opportunities_en",
    "/index_en",
]
# Leading ALL-CAPS country prefix in an NCC list entry.
_COUNTRY = re.compile(r"^([A-Z][A-Z' ]{2,}?)\s+(?=[A-Z][a-z])")


def ingest_eccc_news(**kw) -> list[Item]:
    return scrape_ecl_listing("eccc", "news", NEWS_PAGES, _BASE, **kw)


def ingest_eccc_calls(**kw) -> list[Item]:
    return scrape_ecl_listing("eccc", "call", CALL_PAGES, _BASE, **kw)


def ingest_eccc_governing_board(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(GB_PAGE)
    if r is None:
        return items
    soup = BeautifulSoup(r.text, "html.parser")
    for tr in soup.select("table tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.select("td, th")]
        if len(cells) < 6:
            continue
        country, surname, firstname = cells[0], cells[1], cells[2]
        role_desc = cells[4]
        member_type = cells[5]
        if not country or not surname or country.lower() == "country" or "/" in member_type:
            continue
        link = tr.select_one('a[href]')
        href = link["href"] if link and link.get("href") else None
        url = norm_url(href if href and href.startswith("http") else (_BASE + "/" + href if href else GB_PAGE + f"#{country}-{surname}"))
        if url in seen:
            continue
        seen.add(url)
        name = clean(f"{firstname} {surname}")
        title = clean(f"{country}: {name} ({member_type})" if member_type else f"{country}: {name}")
        body = clean(f"ECCC Governing Board {member_type or 'member'} for {country}: {name}. "
                     f"{role_desc}".strip())
        items.append(Item(body_code="eccc", item_type="governing_board", title=title[:300],
                          public_url=url, summary=role_desc[:200] or None, creation_date=now,
                          source_kind="html", guid=url, body_txt=body,
                          body_html=f"<p>{body}</p>"))
    return items


def ingest_eccc_nccs(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(NCC_PAGE)
    if r is None:
        return items
    main = BeautifulSoup(r.text, "html.parser").select_one("main") or BeautifulSoup(r.text, "html.parser")
    for li in main.select("li"):
        txt = clean(li.get_text(" ", strip=True))
        if len(txt) < 10 or "cookie" in txt.lower() or "skip to" in txt.lower():
            continue
        m = _COUNTRY.match(txt)
        if not m:
            continue
        country = clean(m.group(1)).title()
        rest = clean(txt[m.end():])
        org = clean(re.sub(r"\s*(Learn more|Read more)\.?$", "", rest, flags=re.I))
        if not org:
            continue
        a = li.select_one('a[href]')
        href = a["href"] if a and a.get("href") else None
        url = norm_url(href if href and href.startswith("http") else (_BASE + href if href else NCC_PAGE + f"#{country}"))
        key = f"{country}|{org[:40]}"
        if key in seen:
            continue
        seen.add(key)
        title = clean(f"{country}: {org}")
        body = clean(f"National Coordination Centre for {country}: {org}.")
        items.append(Item(body_code="eccc", item_type="ncc", title=title[:300],
                          public_url=url, creation_date=now, source_kind="html",
                          guid=key, body_txt=body, body_html=f"<p>{body}</p>"))
    return items


def ingest_eccc_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("eccc", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
