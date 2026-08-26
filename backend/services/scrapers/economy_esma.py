"""
ESMA — European Securities and Markets Authority (/api/v2/eu-financial-institutions/esma).

Verified source map (URL-verification pass, api_econ.md L368-414). ESMA's site is a
Drupal 10 mid-migration: /rss.xml carries no dates, there is no sitemap or JSON:API,
and the library search + key-dates pages are JS-rendered. But two streams ARE
server-rendered and paginated:

  - news         : /press-news/esma-news -> article.node--type-news cards with
                   .search-title + .search-date (DD/MM/YYYY) + a bookmark link.
  - publications : /press-news/consultations -> article.node--type-library-document
                   cards (PDF file links; title from the file name, date from the
                   /YYYY-MM/ path segment).

  events         : DEFERRED — ESMA's "key dates" agenda is JS-rendered with no clean
                   server-rendered feed; revisit with deeper Playwright interaction.

Detail pages (news) are server-rendered. No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, parse_listing_date, _iso_dt,
)

_BASE = "https://www.esma.europa.eu"

ESMA_NEWS_PAGES = [f"{_BASE}/press-news/esma-news"]
ESMA_PUB_PAGES = [f"{_BASE}/press-news/consultations"]

_PATH_DATE_RE = re.compile(r"/(\d{4})-(\d{2})/")
_ESMA_REF_RE = re.compile(r"^ESMA[0-9A-Za-z-]+_")


def _date_from_path(url: str) -> datetime | None:
    m = _PATH_DATE_RE.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1, tzinfo=timezone.utc)
    except ValueError:
        return None


def _title_from_filename(name: str) -> str:
    name = name.rsplit(".", 1)[0]          # drop extension
    name = _ESMA_REF_RE.sub("", name)      # drop the ESMA reference prefix
    return clean(name.replace("_", " ").strip()) or name


def _parse_news_page(html: str) -> list[Item]:
    soup = BeautifulSoup(html, "html.parser")
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    for art in soup.select("article.node--type-news"):
        a = art.select_one('a[href*="/press-news/esma-news/"]') or art.find("a", href=True)
        if not a or not a.get("href"):
            continue
        url = norm_url(a["href"] if a["href"].startswith("http") else _BASE + a["href"])
        title_el = art.select_one(".search-title .field--name-title") or art.select_one(".search-title")
        title = clean(title_el.get_text(" ", strip=True)) if title_el else clean(a.get_text(" ", strip=True))
        if not title:
            continue
        date_el = art.select_one(".search-date")
        doc_dt = parse_listing_date(date_el.get_text(" ", strip=True)) if date_el else None
        intro = art.select_one('.field--name-field-news-introduction')
        summary = clean(intro.get_text(" ", strip=True)[:1000]) if intro else None
        out.append(Item(body_code="esma", item_type="news", title=title, public_url=url,
                        summary=summary, document_date=doc_dt, creation_date=now,
                        source_kind="html", guid=url))
    return out


def _parse_pub_page(html: str) -> list[Item]:
    soup = BeautifulSoup(html, "html.parser")
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    for art in soup.select("article.node--type-library-document"):
        a = art.select_one('a[href*="/sites/default/files"]') or art.find("a", href=True)
        if not a or not a.get("href"):
            continue
        url = norm_url(a["href"] if a["href"].startswith("http") else _BASE + a["href"])
        fname = a.get_text(strip=True) or url.rsplit("/", 1)[-1]
        title = _title_from_filename(fname)
        if not title:
            continue
        out.append(Item(body_code="esma", item_type="publication", title=title, public_url=url,
                        document_date=_date_from_path(url), creation_date=now,
                        source_kind="html", guid=url))
    return out


def _scrape_paged(pages, parser, *, fetch_bodies: bool, max_pages: int) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    for base_url in pages:
        for page in range(max_pages):
            sep = "&" if "?" in base_url else "?"
            url = base_url if page == 0 else f"{base_url}{sep}page={page}"
            r = http_get(url)
            if r is None:
                break
            rows = parser(r.text)
            if not rows:
                break
            new = 0
            for it in rows:
                if it.public_url in seen:
                    continue
                seen.add(it.public_url)
                new += 1
                items.append(it)
            if new == 0:
                break
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_esma_news(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    return _scrape_paged(ESMA_NEWS_PAGES, _parse_news_page, fetch_bodies=fetch_bodies, max_pages=max_pages)


def ingest_esma_publications(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    return _scrape_paged(ESMA_PUB_PAGES, _parse_pub_page, fetch_bodies=fetch_bodies, max_pages=max_pages)


# --- ESMA FIRDS: Financial Instruments Reference Data System ----------------
# Reverse-engineering note:
#   FIRDS is ESMA's register of ~30M financial instruments. The Solr search
#   (registers.esma.europa.eu/.../doMainSearch) works for NARROW keyword queries
#   but TIMES OUT on broad ones (wildcard over 30M rows), so it can't list
#   "recent" instruments. The canonical bounded source is the daily DELTA file
#   (DLTINS) — ISO 20022 XML in a zip, listed in the `esma_registers_firds_files`
#   Solr core. We take the latest delta and stream-parse a bounded slice.
#   The search endpoint needs the exact Accept header
#   "application/json, text/javascript, */*; q=0.01" (else it returns HTML) and a
#   prior GET on the register page to establish the session.
_FIRDS_SEARCH = "https://registers.esma.europa.eu/publication/searchRegister/doMainSearch"
_FIRDS_FILES_PAGE = "https://registers.esma.europa.eu/publication/searchRegister?core=esma_registers_firds_files"
_FIRDS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": _FIRDS_FILES_PAGE,
}


def _latest_dltins_link():
    import requests, json as _json, time
    s = requests.Session()
    s.headers.update({"User-Agent": _FIRDS_HEADERS["User-Agent"]})
    for _ in range(4):
        try:
            s.get(_FIRDS_FILES_PAGE, timeout=45)
            break
        except requests.RequestException:
            time.sleep(2)
    body = {"core": "esma_registers_firds_files", "pagingSize": "1", "start": 0,
            "keyword": "DLTINS", "sortField": "publication_date desc", "criteria": [], "wt": "json"}
    for _ in range(3):
        try:
            r = s.post(_FIRDS_SEARCH, headers=_FIRDS_HEADERS, data=_json.dumps(body), timeout=60)
            if r.text.strip().startswith("{"):
                docs = r.json().get("response", {}).get("docs", [])
                if docs:
                    return docs[0].get("download_link"), docs[0].get("publication_date")
        except requests.RequestException:
            time.sleep(2)
    return None, None


def ingest_esma_financial_instruments(*, fetch_bodies: bool = True, max_instruments: int = 5000):
    import io
    import zipfile
    import requests
    from xml.etree import ElementTree as ET

    link, pub = _latest_dltins_link()
    if not link:
        return []
    try:
        zb = requests.get(link, headers={"User-Agent": _FIRDS_HEADERS["User-Agent"]}, timeout=240).content
        z = zipfile.ZipFile(io.BytesIO(zb))
    except (requests.RequestException, zipfile.BadZipFile):
        return []

    def ln(t):
        return t.rsplit("}", 1)[-1]

    def first(el, tag):
        for d in el.iter():
            if ln(d.tag) == tag and d.text:
                return d.text
        return None

    def venue_and_date(el):
        for d in el.iter():
            if ln(d.tag) == "TradgVnRltdAttrbts":
                mic = ftd = None
                for c in d:
                    if ln(c.tag) == "Id" and c.text:
                        mic = c.text
                    elif ln(c.tag) == "FrstTradDt" and c.text:
                        ftd = c.text
                return mic, ftd
        return None, None

    now = datetime.now(timezone.utc)
    items = []
    seen = set()
    with z.open(z.namelist()[0]) as f:
        for _ev, el in ET.iterparse(f, events=("end",)):
            if ln(el.tag) != "FinInstrm":
                continue
            gnl = next((d for d in el.iter() if ln(d.tag) == "FinInstrmGnlAttrbts"), None)
            isin = first(gnl, "Id") if gnl is not None else None
            if isin and isin not in seen:
                seen.add(isin)
                name = clean(first(gnl, "FullNm")) or isin
                cfi = first(gnl, "ClssfctnTp")
                ccy = first(gnl, "NtnlCcy")
                lei = first(el, "Issr")
                mic, ftd = venue_and_date(el)
                doc_dt = _iso_dt(ftd) if ftd else None
                url = norm_url(f"https://registers.esma.europa.eu/publication/searchRegister"
                               f"?core=esma_registers_firds&keyword={isin}")
                lines = [
                    f"ISIN: {isin}", f"Instrument: {name}",
                    f"CFI classification: {cfi}" if cfi else "",
                    f"Notional currency: {ccy}" if ccy else "",
                    f"Issuer (LEI): {lei}" if lei else "",
                    f"Trading venue (MIC): {mic}" if mic else "",
                    f"First trading date: {ftd[:10]}" if ftd else "",
                ]
                lines = [l for l in lines if l]
                items.append(Item(
                    body_code="esma", item_type="financial_instrument", title=name,
                    public_url=url, summary=clean(f"{isin} — {name}" + (f" ({cfi})" if cfi else "")),
                    body_txt=clean("\n".join(lines)),
                    body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
                    document_date=doc_dt, creation_date=now, source_kind="firds", guid=isin))
            el.clear()
            if len(items) >= max_instruments:
                break
    return items
