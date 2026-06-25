"""
CJEU — Court of Justice of the European Union (api_ecj.md). /api/v2/cjeu.

The CJEU's public site is curia.europa.eu, a Jalios JCMS, plus InfoCuria for the
case-law. Source map (verified 25 Jun 2026):
  - press_release : /site/jcms/d2_5158/en/press-releases — li.curia-itemlist-item
                    rows (PR number, a <time datetime="DD/MM/YYYY"> and a title link
                    to the cp...en.pdf). Relative PDF links resolve against the page
                    <base href="https://curia.europa.eu/site/">. Current year (~92).
                    Bodies extracted from the PDFs.
  - case_law      : InfoCuria's case-law is the EU case-law corpus (sector-6 CELEX).
                    InfoCuria itself is a stateful JSF search that cannot be scraped
                    by GET, so the same corpus is read machine-readably from the
                    Publications Office Cellar SPARQL endpoint (which backs InfoCuria
                    and EUR-Lex): every judgment, Advocate General opinion and order
                    of the current year, with its CELEX, ECLI, date and title. The
                    public link is the EUR-Lex CELEX page.
  - event         : /site/jcms/d2_5160/en/events — li.curia-itemlist-item rows.
  - topic         : about + documents-and-research JCMS landing pages.

Reads from economy_items (body row seeded by migration 167); 5 mandatory
datapoints. Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, snapshot_topics,
)

_BASE = "https://curia.europa.eu"
_SITE = "https://curia.europa.eu/site/"  # the page <base href> for relative links
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

PRESS_PAGE = f"{_BASE}/site/jcms/d2_5158/en/press-releases"
EVENTS_PAGE = f"{_BASE}/site/jcms/d2_5160/en/events"

_SPARQL = "http://publications.europa.eu/webapi/rdf/sparql"
_EURLEX_CELEX = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"

_TOPIC_PATHS = [
    "/site/jcms/d2_5088/en/about-the-cjeu",
    "/site/jcms/d2_5100/en/history",
    "/site/jcms/d2_5093/en/the-court-of-justice",
    "/site/jcms/d2_5094/en/the-general-court",
    "/site/jcms/d2_5101/en/court-departments",
    "/site/jcms/d2_5103/en/the-court-in-numbers",
    "/site/jcms/d2_5099/en/impact-of-the-court-s-work-case-law-explained",
    "/site/jcms/d2_5105/en/can-i-bring-my-case-to-the-court",
    "/site/jcms/d2_5108/en/how-the-procedure-works",
    "/site/jcms/d2_5110/en/procedural-texts",
    "/site/jcms/d2_5115/en/e-curia",
    "/site/jcms/d2_5119/en/case-law-database",
    "/site/jcms/d2_5129/en/yearly-selection-of-leading-judgments",
    "/site/jcms/d2_5120/en/european-court-reports",
    "/site/jcms/d2_5126/en/case-law-digest",
    "/site/jcms/d2_5127/en/fact-sheets",
    "/site/jcms/d2_5128/en/monthly-case-law-digest",
    "/site/jcms/d2_5134/en/library",
    "/site/jcms/d2_5135/en/judicial-network-of-the-eu",
    "/site/jcms/d2_5136/en/national-case-law",
    "/site/jcms/d2_5137/en/research-notes",
    "/site/jcms/d2_5138/en/legal-monitoring",
    "/site/jcms/d2_5140/en/annual-report",
    "/site/jcms/d2_5141/en/other-publications-and-reports",
]

_DMY = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def _ddmmyyyy(s: str) -> datetime | None:
    m = _DMY.search(s or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_itemlist(html: str, item_type: str):
    """li.curia-itemlist-item rows -> (url, title, doc_dt, summary, is_pdf)."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for li in soup.select("li.curia-itemlist-item"):
        a = li.select_one(".curia-itemlist-item-title a[href], a[href]")
        if not a or not a.get("href"):
            continue
        href = a["href"]
        if href.startswith("http"):
            url = href
        elif href.startswith("/"):
            url = _BASE + href
        else:
            url = _SITE + href  # relative -> resolve against the page <base href>
        title = clean(a.get_text(" ", strip=True))
        if not title or len(title) < 6:
            continue
        nd = li.select_one(".curia-itemlist-item-numdate")
        t = li.select_one("time[datetime]")
        doc_dt = _ddmmyyyy(t["datetime"]) if t and t.get("datetime") else None
        summary = clean(nd.get_text(" ", strip=True)[:200]) if nd else None
        out.append((norm_url(url), title, doc_dt, summary, ".pdf" in url.lower()))
    return out


def ingest_cjeu_press_releases(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(PRESS_PAGE)
    if r is None:
        return items
    for url, title, doc_dt, summary, is_pdf in _parse_itemlist(r.text, "press_release"):
        if url in seen:
            continue
        seen.add(url)
        items.append(Item(body_code="cjeu", item_type="press_release", title=title[:300],
                          public_url=url, summary=summary, document_date=doc_dt,
                          creation_date=now, source_kind="pdf" if is_pdf else "html", guid=url))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind in ("pdf", "html"):
                it.source_kind = kind
    return items


def ingest_cjeu_events(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(EVENTS_PAGE)
    if r is None:
        return items
    for url, title, doc_dt, summary, is_pdf in _parse_itemlist(r.text, "event"):
        if url in seen:
            continue
        seen.add(url)
        items.append(Item(body_code="cjeu", item_type="event", title=title[:300],
                          public_url=url, summary=summary, document_date=doc_dt,
                          creation_date=now, source_kind="html", guid=url))
    if fetch_bodies:
        for it in items:
            if it.public_url.lower().endswith(".pdf") or "/jcms/" in it.public_url:
                body_txt, body_html, kind = fetch_detail(it.public_url)
                it.body_txt, it.body_html = body_txt, body_html
    return items


_CASE_LAW_QUERY = """
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT DISTINCT ?celex ?date ?ecli ?title WHERE {{
  ?work cdm:resource_legal_id_celex ?celex .
  ?work cdm:work_date_document ?date .
  OPTIONAL {{ ?work cdm:case-law_ecli ?ecli . }}
  OPTIONAL {{
    ?expr cdm:expression_belongs_to_work ?work ;
          cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> ;
          cdm:expression_title ?title .
  }}
  FILTER(STRSTARTS(STR(?celex), "6"))
  FILTER(?date >= "{since}"^^xsd:date)
}}
ORDER BY DESC(?date) STR(?celex)
LIMIT {limit} OFFSET {offset}
"""


def ingest_cjeu_case_law(*, fetch_bodies: bool = True, **_) -> list[Item]:
    """Current-year CJEU case-law (sector-6 CELEX) via the Cellar SPARQL endpoint
    that backs InfoCuria/EUR-Lex. Catalogue-style: structured metadata + the
    EUR-Lex link, no per-document text fetch (the full judgments are large and
    EUR-Lex WAFs unauthenticated clients)."""
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    since = f"{now.year}-01-01"
    page = 500
    for offset in range(0, 4000, page):
        q = _CASE_LAW_QUERY.format(since=since, limit=page, offset=offset)
        try:
            resp = requests.get(_SPARQL, params={"query": q, "format": "application/sparql-results+json"},
                                headers={"User-Agent": _UA, "Accept": "application/sparql-results+json"},
                                timeout=90)
        except requests.RequestException:
            break
        if resp.status_code != 200:
            break
        try:
            rows = json.loads(resp.text)["results"]["bindings"]
        except (ValueError, KeyError):
            break
        if not rows:
            break
        for b in rows:
            celex = b.get("celex", {}).get("value")
            if not celex or celex in seen:
                continue
            seen.add(celex)
            ecli = b.get("ecli", {}).get("value", "")
            dt = b.get("date", {}).get("value", "")
            title = clean(b.get("title", {}).get("value", "")) or f"Case-law document {celex}"
            doc_dt = None
            try:
                doc_dt = datetime.strptime(dt[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                pass
            url = _EURLEX_CELEX.format(celex=celex)
            body = (f"{title}\nECLI: {ecli}\nCELEX: {celex}\nDate: {dt[:10]}\n"
                    f"EUR-Lex: {url}")
            items.append(Item(body_code="cjeu", item_type="case_law", title=title[:300],
                              public_url=url, summary=(ecli or celex)[:200], document_date=doc_dt,
                              creation_date=now, source_kind="cellar_sparql", guid=celex,
                              body_txt=body, body_html=f"<pre>{body}</pre>"))
        if len(rows) < page:
            break
    return items


def ingest_cjeu_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("cjeu", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
