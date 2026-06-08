"""
ECB + ECB Banking Supervision (SSM) ingestion for the /api/v2/ecb folder.

Verified source map (URL-verification pass, api_econ.md L70-279):
  - news         : RSS feeds (/rss/press.html, /rss/blog.html | SSM /rss/press.xml)
                   -> item detail pages are SERVER-RENDERED HTML.
  - publications : RSS feeds (/rss/pub.html, /rss/wppub.html, /rss/statpress.html)
                   -> item detail is HTML or (working papers) PDF.
  - events       : conferences/calendars pages are SERVER-RENDERED (no RSS) -> scrape
                   ECB's date-indexed <dl> (<dt> date + <dd> with div.title) markup.
  - legal        : no RSS -> Cellar SPARQL (ECB as author), the canonical EU source.

The index/list HTML pages are JS-rendered (no items in raw HTML), which is why
discovery goes through RSS, not list-page scraping. ECB RSS item links carry a
doubled slash (ecb.europa.eu//press/...) which we normalise.

Every item carries the 5 mandatory datapoints: public_url, body_txt, body_html,
document_date, creation_date. No LLM is used anywhere in this module.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

import feedparser
import requests
from bs4 import BeautifulSoup

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 BrubruBot/1.0"
_TIMEOUT = 30
_BODY_CAP = 800_000  # chars; working-paper PDFs can be large

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

# JS-rendered listing pages (the date-indexed <dl> is injected client-side, so a
# static fetch returns empty <dd>). Rendered with Playwright; see
# scrape_rendered_listing(). The ECB "calendars" page uses a different layout
# and yields no <dl>, so events come from the "conferences" page.
ECB_EVENT_PAGES = ["https://www.ecb.europa.eu/press/conferences/html/index.en.html"]
SSM_EVENT_PAGES = ["https://www.bankingsupervision.europa.eu/press/conferences/html/index.en.html"]
SSM_PUB_PAGES = ["https://www.bankingsupervision.europa.eu/press/other-publications/publications/html/index.en.html"]

_CELLAR_SPARQL = "http://publications.europa.eu/webapi/rdf/sparql"


@dataclass
class Item:
    body_code: str
    item_type: str            # news | publication | event | legal
    title: str
    public_url: str
    summary: str | None = None
    body_txt: str | None = None
    body_html: str | None = None
    document_date: datetime | None = None
    creation_date: datetime | None = None
    source_kind: str | None = None
    guid: str | None = None
    extras: dict = field(default_factory=dict)


# --- helpers ---------------------------------------------------------------
def _norm_url(url: str) -> str:
    """Fix the doubled slash ECB RSS emits after the host (harmless 200 but ugly)."""
    if not url:
        return url
    url = url.strip()
    m = re.match(r"^(https?://[^/]+)(/.*)$", url)
    if not m:
        return url
    host, path = m.group(1), m.group(2)
    path = re.sub(r"/{2,}", "/", path)
    return host + path


def _http_get(url: str) -> requests.Response | None:
    try:
        r = requests.get(url, headers={"User-Agent": _UA}, timeout=_TIMEOUT, allow_redirects=True)
        if r.status_code == 200:
            return r
    except requests.RequestException:
        return None
    return None


_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")  # C0 controls except \t \n \r


def _clean(s: str | None) -> str | None:
    """Strip NUL + other C0 control chars Postgres TEXT rejects (PDF extraction emits them)."""
    if not s:
        return s
    return _CTRL_RE.sub("", s)


def _to_dt(struct) -> datetime | None:
    if not struct:
        return None
    try:
        return datetime(*struct[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _extract_html(html: str) -> tuple[str | None, str | None]:
    """(body_txt, body_html) from a server-rendered ECB/SSM detail page."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()
    node = soup.find("main") or soup.find("article") or soup.body or soup
    body_html = _clean(str(node)[:_BODY_CAP])
    body_txt = _clean(node.get_text("\n", strip=True)[:_BODY_CAP])
    return (body_txt or None), (body_html or None)


def _extract_pdf(content: bytes) -> str | None:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        parts = []
        total = 0
        for page in reader.pages:
            t = page.extract_text() or ""
            parts.append(t)
            total += len(t)
            if total > _BODY_CAP:
                break
        text = "\n".join(parts).strip()
        return _clean(text[:_BODY_CAP]) or None
    except Exception:
        return None


def _fetch_detail(url: str) -> tuple[str | None, str | None, str]:
    """Return (body_txt, body_html, source_kind) for one item URL."""
    r = _http_get(url)
    if r is None:
        return None, None, "unreachable"
    ctype = (r.headers.get("content-type") or "").lower()
    if "application/pdf" in ctype or url.lower().endswith(".pdf"):
        txt = _extract_pdf(r.content)
        wrapper = f'<p>PDF document: <a href="{url}">{url}</a></p>'
        return txt, wrapper, "pdf"
    body_txt, body_html = _extract_html(r.text)
    return body_txt, body_html, "html"


# --- feed-driven ingestion (news, publications) ----------------------------
def _feed_entries(feed_url: str):
    r = _http_get(feed_url)
    if r is None:
        return []
    parsed = feedparser.parse(r.content)
    return parsed.entries or []


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
            link = _norm_url(getattr(e, "link", "") or "")
            if not link or link in seen:
                continue
            seen.add(link)
            title = _clean((getattr(e, "title", "") or "").strip()) or link
            summary = _clean((getattr(e, "summary", "") or "").strip()) or None
            doc_dt = _to_dt(getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None))
            it = Item(
                body_code=body_code, item_type=item_type, title=title,
                public_url=link, summary=summary, document_date=doc_dt,
                creation_date=now, guid=(getattr(e, "id", None) or link),
                source_kind="rss",
            )
            if fetch_bodies:
                body_txt, body_html, kind = _fetch_detail(link)
                it.body_txt, it.body_html, it.source_kind = body_txt, body_html, kind
            items.append(it)
    return items


def ingest_ecb_news(**kw) -> list[Item]:
    return ingest_feeds("ecb", "news", ECB_FEEDS["news"], **kw)


def ingest_ecb_publications(**kw) -> list[Item]:
    return ingest_feeds("ecb", "publication", ECB_FEEDS["publication"], **kw)


def ingest_ssm_news(**kw) -> list[Item]:
    return ingest_feeds("ecb_ssm", "news", SSM_FEEDS["news"], **kw)


# --- rendered listings (events, SSM publications) --------------------------
# JS-rendered date-indexed <dl> pages. We render with headless Chromium via the
# shared WafBrowserFetcher, then parse <dt>(date) + <dd>(link+title). Two date
# formats appear: "11 May 2026" and "11/06/2026" (ranges -> take the start).
_LONG_DATE_RE = re.compile(r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|"
                           r"September|October|November|December)\s+(\d{4})\b", re.I)
_NUM_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}


def _parse_listing_date(text: str) -> datetime | None:
    text = text or ""
    m = _NUM_DATE_RE.search(text)          # 11/06/2026 (ranges -> first match = start)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            return None
    m = _LONG_DATE_RE.search(text)         # 11 May 2026
    if m:
        try:
            return datetime(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)),
                            tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


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
            base = re.match(r"^(https?://[^/]+)", page).group(1)
            for dd in soup.find_all("dd"):
                a = dd.find("a", href=True)
                if not a:
                    continue
                href = a["href"]
                url = _norm_url(href if href.startswith("http") else base + href)
                if url in seen or "/shared/" in url:
                    continue
                title = _clean(a.get_text(" ", strip=True))
                if not title:
                    continue
                seen.add(url)
                dt_node = dd.find_previous_sibling("dt")
                doc_dt = _parse_listing_date(dt_node.get_text(" ", strip=True)) if dt_node else None
                items.append(Item(
                    body_code=body_code, item_type=item_type, title=title,
                    public_url=url, document_date=doc_dt, creation_date=now,
                    source_kind="html", guid=url,
                ))
    # Detail pages are server-rendered, so bodies fetch cheaply via requests.
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = _fetch_detail(it.public_url)
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
# ECB corporate-body authority code in the EU Publications Office vocabulary.
_ECB_AUTHORITY = "http://publications.europa.eu/resource/authority/corporate-body/ECB"


def fetch_ecb_legal_acts(limit: int = 100) -> list[Item]:
    """ECB legal acts via Cellar SPARQL (author = ECB corporate body).

    Returns dated acts (title, EUR-Lex URL, date). body_txt/body_html stay light
    (title + EUR-Lex link); full text is available on demand via the eur-lex laws
    endpoints. CELEX is taken verbatim from Cellar, never derived.
    """
    query = f"""
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
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
        r = requests.get(
            _CELLAR_SPARQL,
            params={"query": query, "format": "application/sparql-results+json"},
            headers={"User-Agent": _UA, "Accept": "application/sparql-results+json"},
            timeout=60,
        )
        if r.status_code != 200:
            return []
        rows = r.json().get("results", {}).get("bindings", [])
    except (requests.RequestException, ValueError):
        return []

    now = datetime.now(timezone.utc)
    items: list[Item] = []
    for b in rows:
        celex = b.get("celex", {}).get("value")
        title = (b.get("title", {}).get("value") or "").strip()
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
        items.append(Item(
            body_code="ecb", item_type="legal", title=title, public_url=url,
            summary=f"ECB legal act — CELEX {celex}",
            body_html=f'<p>{title}</p><p>CELEX <a href="{url}">{celex}</a></p>',
            body_txt=f"{title}\nCELEX {celex}",
            document_date=doc_dt, creation_date=now, source_kind="cellar",
            guid=celex, extras={"celex": celex},
        ))
    return items
