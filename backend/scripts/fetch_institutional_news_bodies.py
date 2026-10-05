"""Fetch the ACTUAL article for institutional news, instead of composing one.

GovClipping need the whole text in `body_txt` and the whole HTML in `body_html`,
especially on news and publications (Victor, 25 September 2026).

Today every one of the 11,387 `eu_news_items` rows carries a body composed at backfill
time from the title and the RSS summary: `body_source` is `composed:title+summary` (7,995)
or `composed:title` (3,392), averaging 379 characters. That was a deliberate decision on
8 September, taken so the five-datapoint contract would have no nulls, and
`backfill_eu_news_bodies.py` says plainly that it "does NOT fetch the article". It met the
letter of the contract and defeated its purpose, and it made the gap harder to see: a
plausible 379-character body reads as populated where a null would have shouted.

This fetches the page and stores what is actually there. Scope is EU INSTITUTIONAL sources
only. The other 4,320 rows come from Politico, Euractiv and EUobserver, whose article text
is theirs and is not ours to store or serve; those keep title, summary and the link.

Guards, reusing the economy scraper's own helpers so this behaves like the rest of the
corpus: `extract_html()` strips nav/header/footer/script and keeps <main>/<article>, and
`error_body_reason()` refuses to store a cookie wall, a 404 page or anything too short to
be an article. A row that cannot be fetched keeps the body it has.

Usage (from backend/):
    python3.12 scripts/fetch_institutional_news_bodies.py --institution EEA
    python3.12 scripts/fetch_institutional_news_bodies.py --institution EEA --apply
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import os
import re
import sys
import pathlib
import urllib.parse
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.scrapers.economy_common import error_body_reason, extract_html  # noqa: E402
from api.v1._body import body_from_html_or_text  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
# Anything on these hosts is an EU institution or agency: a public document.
INSTITUTIONAL = ("europa.eu", "europarl.europa.eu", "consilium.europa.eu", "ecb.int",
                 # The European Parliamentary Research Service publishes on its own
                 # domain. Verified 25 September 2026: epthinktank.eu/about is titled
                 # "About | Epthinktank | European Parliament" and describes EPRS as the
                 # Parliament's research service. Institutional in substance, whatever
                 # the top-level domain says.
                 "epthinktank.eu",
    # 166 EIB press items sat at title+summary only because the host was not listed.
    "eib.org")


def _cut_to_headline(body: str, title: str | None, window: int = 4000,
                     keep_at_least: int = 200) -> str:
    """Drop the page furniture that precedes the article's own headline.

    Looks only at the head of the text, takes the LAST occurrence there (a breadcrumb
    and the heading often both carry the title), and keeps the cut only when enough
    article survives it.
    """
    if not body or not title:
        return body
    needle = " ".join(title.split())[:70].strip().lower()
    if len(needle) < 15:
        return body
    head = " ".join(body.split()).lower()
    hay = body.lower()
    idx = hay.rfind(needle, 0, window)
    if idx <= 0:
        return body
    cut = body[idx:].strip()
    return cut if len(cut) >= keep_at_least else body


# Where a site's own footer starts. The browser's text read of a Consilium page runs
# past the article into the footer ("About the secretariat ... Cookies"): 85 Council
# bodies carried it on 5 Oct 2026. The article never contains these lines.
_SITE_FOOTER_MARKERS = ("\nAbout the secretariat\n",)


# Where a page's cookie banner and menu end. 44 Council bodies opened with "to improve
# your browsing experience ... I accept only necessary cookies ... Skip to content" and
# the site menu before the release itself (5 Oct 2026). The release follows its own
# "Press release" label, so everything up to that label is page furniture.
_FILE_URL = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|zip)(\?|$)|/document/download/|/pub/pdf/", re.I)
_STOP = set("with from that this have will their which about under into other where after "
            "before being these those between within".split())


def _title_words(s: str | None) -> set:
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return {w for w in re.findall(r"[a-z0-9]{4,}", s) if w not in _STOP}


def _names_item(title: str | None, body: str) -> bool:
    tw = _title_words(title)
    return len(tw) < 3 or len(tw & _title_words(body)) / len(tw) >= 0.35


_BANNER_END = "I accept only necessary cookies"
_NOT_FOUND = re.compile(r"couldn.t find the page|^Page not found$|404 Content is no longer available"
                        r"|429 - Too Many Requests|^Server inaccessibility$",
                        re.I | re.M)
_HEAD_LABELS = ("\nPress release\n", "\nStatement and remarks\n", "\nMedia advisory\n")


def _cut_site_footer(body: str | None) -> str | None:
    if not body:
        return body
    if _BANNER_END in body[:3000]:
        start = body.find(_BANNER_END) + len(_BANNER_END)
        cuts = [body.find(lbl, start) for lbl in _HEAD_LABELS]
        cuts = [c for c in cuts if 0 <= c < start + 2500]
        if cuts:
            c = min(cuts)
            body = body[body.find("\n", c + 1) + 1:].lstrip()
        else:
            k = body.find("Skip to content", start)
            body = body[(k + len("Skip to content")) if k >= 0 else start:].lstrip()
    for marker in _SITE_FOOTER_MARKERS:
        i = body.find(marker)
        if i > 200:
            body = body[:i].rstrip()
    return body


def is_institutional(url: str) -> bool:
    """True when the URL's HOST is one of these domains, or a subdomain of one.

    This used to be a substring test over the whole URL, which is not a host check at all:
    `https://europa.eu.evil.com/a` and `https://notepthinktank.eu.evil.com/a` both passed,
    and so would any path containing the string. A host that merely ENDS with the domain is
    not enough either, hence the dot: `notepthinktank.eu` must not match `epthinktank.eu`.
    """
    host = urllib.parse.urlsplit(url or "").hostname or ""
    host = host.lower().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in INSTITUTIONAL)


_PRESSCORNER = re.compile(r"^https?://ec\.europa\.eu/commission/presscorner/detail/en/([\w-]+)")


def presscorner_pdf(url: str) -> str | None:
    """The print PDF for a presscorner page, or None if this is not one.

    The page itself is a JavaScript shell: 200, ~22 KB, and zero characters of text, and
    Scrape.do returns the same with render=true, so rendering is not the answer. The
    Commission does serve the document, as a PDF, at a mechanical URL:

        /detail/en/speech_26_911  ->  /api/files/document/print/en/speech_26_911/SPEECH_26_911_EN.pdf

    Checked against speech_, ip_ and statement_ documents: 922 to 5,423 characters each.
    (An older note in memory says this endpoint 404s; it answers 200 today.)
    """
    m = _PRESSCORNER.match(url or "")
    if not m:
        return None
    slug = m.group(1)
    return (f"https://ec.europa.eu/commission/presscorner/api/files/document/print/en/"
            f"{slug}/{slug.upper()}_EN.pdf")


# A 429 is a statement about our request RATE, not about the document. Recording one as a
# failure leaves the row permanently empty and reads later as "this body has no text" --
# the euda slice failed 240 of 400 rows this way. So: every thread shares one backoff
# clock, and a rate limit pauses the whole run rather than burning through the queue.
_RATE_LOCK = threading.Lock()
_BACKOFF_UNTIL = 0.0
_RETRY_STATUS = (429, 503)


def _respect_backoff() -> None:
    while True:
        with _RATE_LOCK:
            wait = _BACKOFF_UNTIL - time.time()
        if wait <= 0:
            return
        time.sleep(min(wait, 5.0))


def _note_rate_limit(exc: urllib.error.HTTPError, attempt: int) -> float:
    """Pause every thread. Honour Retry-After when the server sends one."""
    delay = 0.0
    header = exc.headers.get("Retry-After") if exc.headers else None
    if header:
        try:
            delay = float(header.strip())
        except ValueError:
            delay = 0.0
    if delay <= 0:
        delay = min(60.0, 5.0 * (3 ** attempt))
    with _RATE_LOCK:
        global _BACKOFF_UNTIL
        _BACKOFF_UNTIL = max(_BACKOFF_UNTIL, time.time() + delay)
    return delay


def _read(url: str, timeout: int, accept: str = "*/*") -> bytes:
    """Fetch, retrying a rate limit up to 3 times. Other HTTP errors raise at once."""
    last: Exception | None = None
    for attempt in range(3):
        _respect_backoff()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in _RETRY_STATUS:
                raise
            last = exc
            _note_rate_limit(exc, attempt)
    raise last  # type: ignore[misc]


from services.news.rendered_article import (extract_article, looks_like_challenge,
                                            looks_like_chrome, looks_like_listing,
                                            strip_page_furniture, visible_text)


# What counts as a whole body, matching scripts/api_body_coverage.py.
WHOLE_BODY_CHARS = 1200


def _scrapedo_token() -> str | None:
    """SCRAPEDO_API_KEY lives in the REPO-ROOT .env, not backend/.env.

    Scripts run from backend/ load backend/.env and see it unset, which is why it has read
    as "missing" before. Derive the root from this file, never a hardcoded path.
    """
    token = os.environ.get("SCRAPEDO_API_KEY")
    if token:
        return token
    root_env = Path(__file__).resolve().parents[2] / ".env"
    if root_env.is_file():
        for line in root_env.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("SCRAPEDO_API_KEY="):
                return line.split("=", 1)[1].strip() or None
    return None


def _best_extraction(page_html: str) -> tuple[str | None, str | None, str | None]:
    """Whichever extractor reads this template better, not whichever was written last.

    extract_article knows the Europa component library and refuses consent banners and
    listing pages. extract_html is the economy-store extractor and reads templates the
    other one has no selector for: on an FRA case-law page it finds the whole 2,703-character
    record where extract_article finds 287. Run both, keep the longer body that passes the
    furniture checks, so neither template family loses.
    """
    text_a, html_a, reason_a = extract_article(page_html)

    text_b, html_b = extract_html(page_html)
    if text_b and (error_body_reason(text_b) or looks_like_chrome(text_b)
                   or looks_like_listing(text_b) or looks_like_challenge(text_b)):
        text_b, html_b = None, None

    if text_a and text_b:
        return (text_a, html_a, None) if len(text_a) >= len(text_b) else (text_b, html_b, None)
    if text_a:
        return text_a, html_a, None
    if text_b:
        return text_b, html_b, None
    return None, None, reason_a


_browser_local = threading.local()


def _browser_download(url: str) -> bytes | None:
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_context(accept_downloads=True, user_agent=UA).new_page()
                with page.expect_download(timeout=90000) as dl:
                    try:
                        page.goto(url)
                    except Exception:  # noqa: BLE001  the goto aborts when the download starts
                        pass
                return Path(dl.value.path()).read_bytes()
            finally:
                browser.close()
    except Exception:  # noqa: BLE001
        return None


def _browser_page(url: str, why_paid_failed: str) -> tuple[str | None, str | None, str | None]:
    """The free fallback when Scrape.do is missing, spent or failing: a local browser.

    One headless browser per worker thread, opened on first use and kept for the run
    (Playwright's sync API is thread-affine, so the pool's threads cannot share one).
    It clears JS challenges and renders the page, which covers the Angular shells
    ``render=true`` was for. It does NOT beat an IP-reputation block from this address;
    that is the one thing only the paid proxies do.
    """
    fetcher = getattr(_browser_local, "fetcher", None)
    try:
        if "consilium.europa.eu" in url:
            # Consilium serves a kept browser one page, then bot-challenges every next one
            # (5 of 6 on 5 Oct 2026, one worker). A fresh browser per page passes each time.
            from services.scrapers.waf_browser_fetcher import fetch_one
            res = fetch_one(url, expand_accordions=False, strip_chrome=False)
        elif fetcher is None:
            from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
            fetcher = WafBrowserFetcher()
            fetcher.__enter__()
            _browser_local.fetcher = fetcher
            res = fetcher.fetch(url, expand_accordions=False, strip_chrome=False)
        else:
            res = fetcher.fetch(url, expand_accordions=False, strip_chrome=False)
    except Exception as exc:  # noqa: BLE001  no Playwright, or Chromium failed to start
        if "Download is starting" in str(exc):
            # Consilium serves its research-paper PDFs only as a browser download
            # (ART-2025-2122, 5 Oct 2026): catch the download and parse it.
            raw = _browser_download(url)
            if raw and looks_like_pdf(raw):
                pdf = _pdf_text(raw)
                if pdf and len(pdf) >= 200:
                    return pdf, None, None
        return None, None, f"{why_paid_failed}; browser {type(exc).__name__}"
    if res.error or not res.html:
        return None, None, f"{why_paid_failed}; browser {res.error or 'empty page'}"
    from_po = _from_publications_office(res.html)
    if from_po:
        return from_po, None, None

    text_, html_, reason = _best_extraction(res.html)

    # A rendered page is often still only a record: EDA's report pages render to ~1,400
    # characters of description and a single Download link to the actual report. Follow it,
    # exactly as the direct path does, and keep whichever is longer.
    if len(text_ or "") < WHOLE_BODY_CHARS:
        from_pdf = _follow_to_pdf(res.html, url)
        if from_pdf and len(from_pdf) > len(text_ or ""):
            return from_pdf, None, None

    # The browser's own text extraction beats ours on some templates, because it reads what
    # the page actually renders rather than guessing a container. Use it when it is richer
    # and passes the same furniture checks.
    if len(res.text or "") > len(text_ or ""):
        candidate = strip_page_furniture(res.text)
        if (not looks_like_challenge(candidate) and not looks_like_listing(candidate)
                and len(candidate) >= 200):
            return candidate, None, None

    return text_, html_, (reason if text_ else f"{why_paid_failed}; browser: {reason}")


def fetch_via_scrapedo(url: str, timeout: int = 150, render: bool = True
                       ) -> tuple[str | None, str | None, str | None]:
    """A page Brubru cannot fetch directly, via Scrape.do.

    Two distinct jobs. `render=False` is one credit and defeats an IP-reputation block or a
    rate limit, which is what a 403 or a persistent 429 from an agency site means. `render=True`
    additionally runs the page

    customWait is not optional: without it the service returns the Angular shell with a 200,
    which is a failure carried in the body. 5s was enough on every page tested; 10s added
    nothing.
    """
    from services.scrapers import scrapedo_quota

    token = _scrapedo_token()
    if not token:
        return _browser_page(url, "no SCRAPEDO_API_KEY")
    if scrapedo_quota.is_exhausted():
        return _browser_page(url, "scrapedo quota spent")
    api = ("https://api.scrape.do/?token=" + token
           + "&url=" + urllib.parse.quote(url, safe=""))
    if render:
        api += "&render=true&customWait=5000"
    # The render can come back unrendered: the same URL returned the Angular shell once and
    # the full 101 KB page on the next two calls, all with HTTP 200. A transient must be
    # retried, not filed as "this page has no text".
    last: tuple[str | None, str | None, str | None] = (None, None, "scrapedo not attempted")
    for attempt in range(3):
        try:
            raw = _read(api, timeout, accept="text/html,*/*")
        except urllib.error.HTTPError as exc:
            try:
                scrapedo_quota.note(exc.code, exc.read()[:400])
            except Exception:  # noqa: BLE001
                pass
            return _browser_page(url, f"scrapedo HTTP {exc.code}")
        except Exception as exc:  # noqa: BLE001
            return _browser_page(url, f"scrapedo {type(exc).__name__}")
        last = _best_extraction(raw.decode("utf-8", "replace"))
        if last[0] or not render or "did not render" not in (last[2] or ""):
            return last
        time.sleep(2 * (attempt + 1))
    return last


_CELEX_IN_URL = re.compile(r"(?i)CELEX(?::|%3A)([0-9][0-9A-Z()._-]{4,})")


def _celex_from_url(url: str) -> str | None:
    match = _CELEX_IN_URL.search(url or "")
    return match.group(1).rstrip("&") if match else None


def fetch_cellar(celex: str, timeout: int = 90) -> tuple[str | None, str | None, str | None]:
    """`celex` may also be a Publications Office cellar UUID; the resource path differs."""
    """The document itself, from the Publications Office, not the portal around it.

    EUR-Lex renders a page; Cellar serves the act. For CJEU judgment 62024TJ0239 the rendered
    EUR-Lex page yields 116,974 characters opening with "Skip to main content ... Help Print
    Menu", and Cellar yields 113,938 opening with "JUDGMENT OF THE GENERAL COURT". Same
    document, none of the furniture, one request instead of a render.

    Accept-Language is required (a work-level request without one is rejected), and the type
    must be text/html: these works hold no XHTML datastream.
    """
    kind = "cellar" if re.fullmatch(r"[0-9a-f-]{36}", celex or "") else "celex"
    url = f"https://publications.europa.eu/resource/{kind}/{celex}"
    # Which manifestation a work holds varies by act, and asking for the wrong one is a flat
    # 404, not a redirect to what exists: CJEU judgment 62024TJ0239 serves text/html and has
    # no XHTML, ECB decision 32026D2039 serves application/xhtml+xml and has no HTML. Try
    # both before concluding the document is not there.
    last_reason = "cellar not attempted"
    # application/pdf last: JRC reports and other Publications Office works are PDF-ONLY in
    # Cellar (404 for both HTML types, 200 and 3.4 MB for the PDF), and going to the portal
    # page instead returns op.europa.eu portlet furniture -- "Web Content Display (Global) /
    # For a better user experience ... / Add to my publications / Rate this publication" --
    # with the abstract somewhere below it.
    for accept in ("text/html", "application/xhtml+xml", "application/pdf"):
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": accept, "Accept-Language": "eng"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            last_reason = f"cellar HTTP {exc.code} for {accept}"
            continue
        except Exception as exc:  # noqa: BLE001
            return None, None, f"cellar {type(exc).__name__}"
        if looks_like_pdf(raw):
            body_txt = _pdf_text(raw)
            if body_txt and len(body_txt) >= WHOLE_BODY_CHARS:
                return body_txt, None, None
            last_reason = f"cellar pdf gave {len(body_txt or '')} characters"
            continue
        page = raw.decode("utf-8", "replace")
        body_txt = visible_text(page)
        if len(body_txt) >= WHOLE_BODY_CHARS:
            return body_txt, page, None
        last_reason = f"cellar returned {len(body_txt)} characters for {accept}"
    return None, None, last_reason


def _pdf_text(raw: bytes) -> str | None:
    """Text from PDF BYTES, or None. Never the bytes themselves.

    A direct PDF link decoded as UTF-8 produces "%PDF-1.7 %\xc3\xa3\xcf\xd3 1 0 obj
    </Metadata ...", which is long, looks like text to every length check, and is what 118
    CJEU press releases and 17 ECB documents were holding as their article -- one ECB row at
    623,585 characters of it.
    """
    try:
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        pages = [(page.extract_text() or "") for page in reader.pages[:120]]
    except Exception:  # noqa: BLE001
        return None
    text = "\n".join(pages).strip()
    return text or None


def _office_text(raw: bytes) -> str | None:
    """Text of a .docx / .pptx / .xlsx, or of the PDFs and Office files inside a .zip."""
    import io
    import zipfile
    from xml.etree import ElementTree as ET
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        return None
    names = z.namelist()

    def runs(xml: bytes, para_tag: str, text_tag: str) -> list[str]:
        out = []
        for el in ET.fromstring(xml).iter():
            if el.tag.endswith(para_tag):
                t = "".join(x.text or "" for x in el.iter() if x.tag.endswith(text_tag)).strip()
                if t:
                    out.append(t)
        return out

    if "word/document.xml" in names:
        return "\n".join(runs(z.read("word/document.xml"), "}p", "}t")) or None
    if any(n.startswith("ppt/slides/slide") for n in names):
        slides = sorted(n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n))
        return "\n".join(t for n in slides for t in runs(z.read(n), "}p", "}t")) or None
    if "xl/sharedStrings.xml" in names:
        return "\n".join(runs(z.read("xl/sharedStrings.xml"), "}si", "}t")) or None
    parts = []
    for n in names:
        if n.lower().endswith(".pdf"):
            parts.append(_pdf_text(z.read(n)) or "")
        elif n.lower().endswith((".docx", ".pptx", ".xlsx")):
            parts.append(_office_text(z.read(n)) or "")
    return "\n\n".join(p for p in parts if p).strip() or None


def _ocr_pdf(raw: bytes, max_pages: int = 60) -> str | None:
    """Text of an image-only PDF via pdftoppm + tesseract (English model), or None."""
    import shutil
    import subprocess
    import tempfile
    if not (shutil.which("pdftoppm") and shutil.which("tesseract")):
        return None
    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d) / "in.pdf"
        pdf.write_bytes(raw)
        try:
            subprocess.run(["pdftoppm", "-r", "200", "-l", str(max_pages), "-png", str(pdf),
                            str(Path(d) / "p")], check=True, capture_output=True, timeout=600)
        except (subprocess.SubprocessError, OSError):
            return None
        pages = []
        for img in sorted(Path(d).glob("p-*.png")):
            try:
                out = subprocess.run(["tesseract", str(img), "-", "-l", "eng"],
                                     capture_output=True, timeout=180, text=True)
                pages.append(out.stdout.strip())
            except (subprocess.SubprocessError, OSError):
                continue
    # The English model turns other scripts into consonant soup ("UGHWUSULEU3SPL" for
    # the Armenian half of an EPPO working arrangement). Keep a line only when most of
    # its words are real words; refuse the page set when little survives.
    words = _english_words()
    kept, total = [], 0
    for page in pages:
        for line in page.splitlines():
            toks = re.findall(r"[A-Za-z]{3,}", line)
            if not toks:
                continue
            total += 1
            if words is None or sum(t.lower() in words for t in toks) / len(toks) >= 0.6:
                kept.append(line.strip())
    if not kept or (total and len(kept) / total < 0.3):
        return None
    return "\n".join(kept)


_WORDS: set | None = None


def _english_words() -> set | None:
    global _WORDS
    if _WORDS is None:
        try:
            _WORDS = {w.strip().lower() for w in open("/usr/share/dict/words", encoding="utf-8")}
        except OSError:
            return None
    return _WORDS


def looks_like_pdf(raw: bytes) -> bool:
    return raw[:5] == b"%PDF-" or raw[:1024].lstrip()[:5] == b"%PDF-"


_PDF_LINK = re.compile(r'href="([^"]+?\.pdf[^"]*)"', re.I)
_PDF_DOWNLOAD = re.compile(r'href="([^"]*/document/download/[^"]+)"', re.I)


_PO_PUBLICATION_UUID = re.compile(
    r"/publication/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", re.I)


def _from_publications_office(html: str, timeout: int = 90) -> str | None:
    """The document behind a Publications Office record page, via Cellar.

    Called BEFORE judging the page text, not after. The record page renders ~4,600 characters
    of portlet furniture ("Web Content Display (Global) / Add to my publications / Rate this
    publication"), which sails past any length test, so a "page looks thin" condition never
    fires and the document is never fetched. A PO record is never the document, however long
    its chrome is.
    """
    found = _PO_PUBLICATION_UUID.search(html or "")
    if not found:
        return None
    text_, _html, _reason = fetch_cellar(found.group(1).lower(), timeout=timeout)
    return text_


def _follow_to_pdf(html: str, page_url: str, timeout: int = 60) -> str | None:
    """The document a record page links to, when the page itself is only metadata.

    An EU publication landing page is frequently a record: "Details / Publication date /
    Author / Files" and a link. Extracting it yields ~300 characters of field labels, which
    is not the report. The European School of Administration's annual report is 19,337
    characters inside the PDF the page links to.

    Candidates are fetched and the LONGEST text wins, which also settles annex-versus-main
    without pattern-matching filenames: a record often links both, in either order.
    """
    # A Publications Office record carries the work's cellar UUID in its own links. Cellar
    # serves the document; the portal page serves portlet furniture with the abstract buried
    # in it. Go to Cellar first: 302,176 characters of the JRC ranking-method report against
    # 2,877 of "Web Content Display (Global) / Add to my publications / Rate this publication".
    uuid = re.search(r"/publication/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
                     html or "", re.I)
    if uuid:
        from_cellar, _html, _reason = fetch_cellar(uuid.group(1).lower(), timeout=max(timeout, 90))
        if from_cellar:
            return from_cellar

    candidates: list[str] = []
    for pattern in (_PDF_LINK, _PDF_DOWNLOAD):
        for href in pattern.findall(html or ""):
            absolute = urllib.parse.urljoin(page_url, href)
            if absolute not in candidates:
                candidates.append(absolute)
    best = None
    for link in candidates[:3]:   # bounded: a record page links a handful, not hundreds
        try:
            raw = _read(link, timeout, accept="application/pdf,*/*")
        except Exception:  # noqa: BLE001
            continue
        if not looks_like_pdf(raw):
            continue
        text = _pdf_text(raw)
        if text and (best is None or len(text) > len(best)):
            best = text
    return best


def fetch(url: str, timeout: int = 40, render: bool = False) -> tuple[str | None, str | None, str | None]:
    """(body_txt, body_html, error). Never raises: a failure leaves the row alone."""
    # An EUR-Lex link is a link to a document Cellar holds. Go to the source.
    if "eur-lex.europa.eu" in (url or ""):
        celex = _celex_from_url(url)
        if celex:
            body_txt, body_html, reason = fetch_cellar(celex)
            if body_txt:
                return body_txt, body_html, None
            # Fall through: the portal page is better than nothing if Cellar has no copy.

    pdf_url = presscorner_pdf(url)
    if pdf_url:
        try:
            raw = _read(pdf_url, timeout)
            import io

            from pypdf import PdfReader

            txt = "\n".join((pg.extract_text() or "")
                             for pg in PdfReader(io.BytesIO(raw)).pages).strip()
            # No body_html: this is a PDF, and inventing HTML from one is what produced
            # the composed stubs in the first place.
            if txt:
                return txt, None, None
            pdf_problem = "presscorner pdf had no text"
        except urllib.error.HTTPError as exc:
            # The print PDF exists for some item types and not others: speech_26_911 serves
            # one, ip_26_1129 and ip_25_2000 return 404 while their detail pages are 200.
            # That is a missing PDF, not a missing article, so fall through to the page
            # itself rather than returning -- 22 rows were filed as unreachable this way.
            pdf_problem = f"presscorner HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001
            pdf_problem = f"presscorner {type(exc).__name__}"

        if not render:
            return None, None, pdf_problem
        # The detail page is an Angular app; rendered it carries the article (3,483
        # characters for ip_26_1129, which has no print PDF at all).
        text_, html_, reason = fetch_via_scrapedo(url, render=True)
        if text_:
            return text_, html_, None
        return None, None, f"{pdf_problem}; rendered: {reason}"

    try:
        raw = _read(url, timeout, accept="text/html,*/*")
        if looks_like_pdf(raw):
            # A PDF is a document, not a page. Parse it or refuse it; never store the bytes.
            body_txt = _pdf_text(raw)
            if not body_txt or len(body_txt) < 200:
                # A scanned PDF has no text layer: EPPO working arrangements, SRB and ESRB
                # letters (about 160 rows, 5 Oct 2026). OCR reads the page images.
                body_txt = _ocr_pdf(raw)
            if body_txt and len(body_txt) >= 200:
                return body_txt, None, None
            return None, None, "pdf carried no extractable text"
        if raw[:4] == b"PK\x03\x04":
            # An Office file or a zip is a document too. 229 were stored as their raw
            # bytes decoded to text (5 Oct 2026): ESMA reply forms, EBA DPM packages.
            body_txt = _office_text(raw)
            if body_txt and len(body_txt) >= 200:
                return body_txt, None, None
            return None, None, "office/zip file carried no readable text"
        if b"\x00" in raw[:2000]:
            return None, None, "binary file, not a page"
        html = raw.decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        # A wall is not an absence of text. 403 means our address is blocked and a 429 that
        # survived three backoffs means the same in practice; Scrape.do fetches from
        # elsewhere for one credit. Without this the row is filed as having no body.
        if render and exc.code in (403, 429, 503):
            text_, html_, reason = fetch_via_scrapedo(url, render=False)
            if text_:
                return text_, html_, None
            if reason and "did not render" in reason:
                return fetch_via_scrapedo(url, render=True)
            return None, None, f"HTTP {exc.code}; scrapedo: {reason}"
        if exc.code in (403, 429, 503):
            # The paid route was not asked for, but a wall still is not an absence of
            # text: a real browser from this same address clears consilium.europa.eu,
            # which refuses plain HTTP with 403 (152 Council rows were filed as having
            # no body). Free, so it is tried before any credit is spent, and Scrape.do
            # stays the answer when the block follows the address rather than the client.
            text_, html_, browser_reason = _browser_page(url, f"HTTP {exc.code}")
            if text_:
                return text_, html_, None
            return None, None, f"HTTP {exc.code}; {browser_reason}"
        return None, None, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        # A host that DROPS the connection is walling us just as surely as one that
        # answers 403, but it arrives as an exception rather than a status, so it never
        # reached the escalation above: all 37 EU-OSHA rows failed with
        # RemoteDisconnected while a browser reads osha.europa.eu perfectly well.
        text_, html_, browser_reason = _browser_page(url, type(exc).__name__)
        if text_:
            return text_, html_, None
        return None, None, f"{type(exc).__name__}; {browser_reason}"
    # Name the wall from the RAW page, before extraction. The shared extractor now refuses a
    # challenge by returning nothing, which is right for storage and useless for diagnosis:
    # "no text in the page" and "the host is blocking us" need different responses, and the
    # tally is how a run reports which it met.
    if looks_like_challenge(visible_text(html)):
        # A wall on the DIRECT route is a reason to try the other routes, not to stop. The
        # JRC repository rejects plain HTTP with 244 bytes and serves the browser 3,333
        # characters; returning here made "blocked" final and lost 2 of 10 reports.
        if render:
            text_, html_, reason = fetch_via_scrapedo(url, render=True)
            if text_:
                return text_, html_, None
            return None, None, f"bot challenge; {reason}"
        return None, None, "bot challenge, not the document: back off and retry later"

    from_po = _from_publications_office(html)
    if from_po:
        return from_po, None, None

    body_txt, body_html = extract_html(html)

    # A record page is not the document. When what we extracted is too thin to be the
    # publication, follow the file it links to before giving up on it.
    if len(body_txt or "") < WHOLE_BODY_CHARS:
        from_pdf = _follow_to_pdf(html, url, timeout)
        if from_pdf and len(from_pdf) > len(body_txt or ""):
            return from_pdf, None, None

    if looks_like_challenge(body_txt or ""):
        # Never stored, never solved. The row keeps whatever it had and is retried later.
        return None, None, "bot challenge, not the document: back off and retry later"
    if looks_like_chrome(body_txt or ""):
        # Strip the furniture, then judge what is left. 120 ECA rows held exactly 307
        # characters of "Skip to content ... We use cookies ... Refuse Accept Title modal" and
        # nothing else; 110 EU-OSHA rows held the same opening FOLLOWED by a real article.
        # Refusing both would throw away the second kind, storing both keeps navigation in the
        # text a partner searches.
        body_txt = strip_page_furniture(body_txt or "")
        if len(body_txt) < 200:
            return None, None, "page furniture, not the document"
    reason = error_body_reason(body_txt)
    if reason or not body_txt:
        if render:
            # The page carried no prose of its own. On Europa that usually means an Angular
            # shell, so ask for it rendered rather than recording "no text available".
            return fetch_via_scrapedo(url, render=True)
        # Still an Angular shell, and --render was not asked for. The LOCAL browser renders
        # it for nothing, so "no text in the page" was never the end of the ladder: it only
        # meant the cheapest route failed. All 788 Funding & Tenders Portal rows sat at
        # composed:title+summary because of this, and the portal renders ~1,800 characters
        # of article once JavaScript runs. Scrape.do is not the answer here: its free tier
        # is 1,000 requests a MONTH, which one backfill of this size would exhaust.
        text_, html_, browser_reason = _browser_page(url, "no prose in the direct fetch")
        if text_:
            return text_, html_, None
        return None, None, f"rejected:{reason or 'no text in the page'}; {browser_reason}"
    return body_txt, body_html, None



def _reconnect_on_drop(db):
    """Return a session that can execute, reopening it if the server dropped the old one.

    A cheap round trip is the only way to find out: Supabase closes an idle connection
    from its side, and the failure surfaces on the next statement, whichever that is.
    """
    from sqlalchemy.exc import OperationalError
    try:
        db.execute(text("SELECT 1"))
        return db
    except OperationalError:
        print("  [db] connection dropped: reopening the session", flush=True)
        try:
            db.rollback()
            db.close()
        except Exception:  # noqa: BLE001
            pass
        return SessionLocal()


def _commit(db):
    """Commit, reopening the session if the server has dropped it.

    These runs hold one Session across hours of network work, and Supabase closes an idle
    connection from its side. `pool_pre_ping` cannot help: it validates on CHECKOUT, and
    the connection is checked out for the whole run. The EESC backfill died at 652 rows
    with "server closed the connection unexpectedly" after fetching them all.

    Returns the session to keep using, which may be a new one.
    """
    from sqlalchemy.exc import OperationalError
    try:
        db.commit()
        return db
    except OperationalError as exc:
        print(f"  [db] {type(exc).__name__}: reopening the session", flush=True)
        try:
            db.rollback()
            db.close()
        except Exception:  # noqa: BLE001
            pass
        return SessionLocal()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--institution", help="eu_news_items.institution, e.g. EEA")
    ap.add_argument("--body-code", help="economy_items.body_code, e.g. eea. This is the "
                                        "table /api/v2/news/all actually serves when an "
                                        "article exists in both.")
    ap.add_argument("--item-type", action="append",
                    help="economy_items.item_type; repeatable. Default: news.")
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--throttle", type=float, default=1.0)
    ap.add_argument("--workers", type=int, default=6,
                    help="Parallel fetches. Lower it for a host that answers a polite "
                         "single stream but challenges a burst: consilium.europa.eu "
                         "served one browser fetch fine and bot-challenged 28 of 40 at "
                         "six workers (28 Sep 2026). Concurrency is what it objects to, "
                         "not us, so the answer is to slow down, never to solve it.")
    ap.add_argument("--render", action="store_true",
                    help="Fall back to a rendered fetch (Scrape.do) when a page carries no prose. "
                         "Costs credits, so it is opt-in.")
    ap.add_argument("--empty-only", action="store_true",
                    help="Only rows with no body at all (body-code mode). A short body is "
                         "often the source's whole text: Cedefop news fetched shorter than "
                         "stored on 10 of 10 (5 Oct 2026).")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        if args.body_code:
            types = args.item_type or ["news"]
            rows = db.execute(text(
                "SELECT id, public_url AS source_url, coalesce(length(body_txt),0) AS blen, "
                "       '' AS src, left(coalesce(title,''),70) AS title "
                "FROM economy_items WHERE body_code = :code AND item_type = ANY(:types) "
                "  AND public_url IS NOT NULL "
                # The same resume filter the eu_news_items branch has had all along, which
                # this one never got: without it the job re-downloads rows that ALREADY hold
                # a whole body. It is why a euda slice spent 400 requests to earn 240 rate
                # limits, and why a sample of fra/case_law came back holding 16,215
                # characters on every row. Thin rows are the work; full rows are done.
                "  AND coalesce(length(body_txt), 0) < :whole "
                "ORDER BY document_date DESC NULLS LAST, id LIMIT :n"),
                {"code": args.body_code, "types": types, "n": args.limit,
                 "whole": 1 if args.empty_only else WHOLE_BODY_CHARS}).fetchall()
            label = f"{args.body_code}/{','.join(types)}"
        else:
            rows = db.execute(text(
                "SELECT id, source_url, coalesce(length(body_txt),0) AS blen, "
                "       coalesce(body_source,'') AS src, left(coalesce(title,''),70) AS title "
                # Skip what is already fetched. Without this the job re-downloads every
                # article on every run: a restart began COMMISSION again from the top,
                # 1,051 rows already done, and 47 institutions would have paid that twice.
                "FROM eu_news_items WHERE institution = :inst "
                # The resume guard must not trust the marker alone. On 1 Oct 2026
                # all 35 ECA rows carried body_source='fetched:article' while 31
                # held NO text, so the guard excluded them for good: a row that
                # failed was indistinguishable from one that succeeded, and the
                # only sign was an endpoint quietly serving empty bodies. A row
                # with nothing in it has not been fetched, whatever it is marked.
                "  AND coalesce(body_source, '') NOT LIKE 'unfetchable:%%' "
                "  AND (coalesce(body_source, '') <> 'fetched:article' "
                "       OR coalesce(length(body_txt), 0) = 0 "
                # A stored page that kept the site footer and lost the article (29 Council
                # rows on 5 Oct 2026: "About the secretariat ... Cookies") is not fetched
                # either, whatever its marker says.
                "       OR body_txt LIKE '%About the secretariat%') "
                "ORDER BY news_date DESC NULLS LAST, id LIMIT :n"),
                {"inst": args.institution, "n": args.limit}).fetchall()
            label = args.institution
        targets = [r for r in rows if is_institutional(r.source_url)]
        skipped = len(rows) - len(targets)
        print(f"[INFO] {len(rows)} {label} row(s); {len(targets)} on institutional "
              f"hosts, {skipped} skipped as third-party")
        if not targets:
            return 0

        before = sum(r.blen for r in targets) / len(targets)
        print(f"[INFO] average body now: {before:,.0f} characters")

        ok = failed = 0
        gained = []
        reasons: dict[str, int] = {}
        # Fetched in parallel and committed per batch: 7,050 institutional news rows one at
        # a time is hours, and a single commit at the end means a run that dies writes
        # nothing.
        BATCH = 40
        i = 0
        for start in range(0, len(targets), BATCH):
            chunk = targets[start:start + BATCH]
            with cf.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
                fetched = list(ex.map(lambda row: (row, *fetch(row.source_url, render=args.render)), chunk))
            # The batch's fetches took minutes, and Supabase closes an idle connection
            # from its side. The write itself meets that, not only the commit: the
            # Council run died inside an UPDATE with "SSL connection has been closed
            # unexpectedly" although _commit already knew how to reopen. Checked once
            # per batch, not per row.
            if args.apply:
                db = _reconnect_on_drop(db)
            for r, body_txt, body_html, err in fetched:
                i += 1
                # extract_html() returns (None, None) for a page with no <main>/<article>
                # text, and error_body_reason(None) is None because "absent" is not
                # "invalid". So a clean fetch can still carry no body, and len(None) then
                # killed the whole run.
                if err or not body_txt:
                    failed += 1
                    why = err or "no text in page"
                    # Tallied, not just the first ten printed: with 159 failures in a
                    # batch the first ten say nothing about the shape of the problem.
                    reasons[why] = reasons.get(why, 0) + 1
                    if failed <= 5:
                        print(f"  [{i:5}] {why:22} {r.title[:50]}", flush=True)
                    continue
                # An article starts at its own headline. A rendered SPA hands back the
                # whole portal before the piece: all 788 Funding & Tenders rows came out
                # as 2,300 characters that opened with a cookie banner and the left nav,
                # which passes any length check while being furniture. Chasing each
                # portal's nav labels does not generalise and is dangerous, because the
                # match is a prefix test ("en" would eat "Energy..."). The row's own
                # title is the reliable marker, so anything before its last occurrence
                # near the top is dropped. Only applied when that leaves a real body,
                # so a page that merely repeats its title is never emptied.
                body_txt = _cut_to_headline(body_txt, r.title)

                # NUL and lone surrogates: PostgreSQL rejects the first outright and the
                # second cannot be encoded to UTF-8 at all. Both have killed a run.
                def _clean(v):
                    if not v:
                        return None
                    v = v.replace("\x00", "").encode("utf-8", "ignore").decode("utf-8", "ignore")
                    return v or None

                body_txt = _clean(_cut_site_footer(body_txt))
                # A page links other documents, and following the wrong one stored another
                # text under this title (a KIDS Act release under a Portugal aid item, a
                # Dushanbe speech under a Termez one; 21 rows, 5 Oct 2026). Text taken from a
                # web page must name its item; a direct file link is the item itself.
                if body_txt and not _FILE_URL.search(r.source_url or "") and not _names_item(r.title, body_txt):
                    failed += 1
                    reasons["text does not name the item"] = reasons.get("text does not name the item", 0) + 1
                    continue
                # Whatever path produced it, bytes decoded as text are not a body (an EBA zip
                # inside a zip slipped past the download check, 5 Oct 2026).
                if body_txt and (body_txt.startswith("PK\x03\x04")
                                 or body_txt[:2000].count("\ufffd") > 20):
                    failed += 1
                    reasons["binary file, not text"] = reasons.get("binary file, not text", 0) + 1
                    continue
                # A site's own "page not found" page, served with a 200 behind a cookie
                # banner, was stored as the article on 16 Council rows (5 Oct 2026).
                if body_txt and _NOT_FOUND.search(body_txt[:2500]):
                    failed += 1
                    reasons["the page says it does not exist"] = reasons.get("the page says it does not exist", 0) + 1
                    continue
                body_html = _clean(body_html)
                # The text path (browser, PDF) returns no HTML. Keeping the row's old HTML
                # then paired a full text with the old title+summary card (5 Oct 2026), so
                # the HTML is marked up from the text we are storing instead.
                if body_txt and not body_html:
                    body_html = body_from_html_or_text(body_txt)[0]
                if not body_txt:
                    failed += 1
                    reasons["nothing left after cleaning"] = reasons.get("nothing left after cleaning", 0) + 1
                    continue

                # Never shorten a body. A dry run on cedefop/news offered 309 characters for
                # rows already holding 2,796, and euda/publication 5,282 for rows holding
                # 10,600: the listing page is sometimes richer than the article page behind
                # it. Overwriting on "we fetched something" would have degraded 55 slices.
                if len(body_txt) <= (getattr(r, "blen", 0) or 0):
                    failed += 1
                    why = "fetched body is shorter than the stored one"
                    reasons[why] = reasons.get(why, 0) + 1
                    continue
                ok += 1
                gained.append(len(body_txt))
                if args.apply:
                    if args.body_code:
                        db.execute(text(
                            # fetched_at: economy_items has no updated_at either. Both
                            # tables were guessed and both failed the whole batch; the
                            # column list is one query away and worth the query.
                            "UPDATE economy_items SET body_txt = :t, "
                            # COALESCE, never a bare assignment: the PDF branch
                            # returns no HTML on purpose, and writing that NULL
                            # DESTROYED the HTML the row already had. On 1 Oct 2026
                            # this emptied body_html on 1,074 rows it had just
                            # given good text to. Never shorten a value you are
                            # backfilling.
                            "  body_html = COALESCE(CAST(:h AS text), body_html), "
                            "  fetched_at = now() WHERE id = :id"),
                            {"t": body_txt, "h": body_html, "id": r.id})
                    else:
                        db.execute(text(
                            "UPDATE eu_news_items SET body_txt = :t, "
                            "  body_html = COALESCE(CAST(:h AS text), body_html), "
                            # fetched_at, not last_updated: eu_news_items has no such
                            # column and the whole batch failed on it the first time.
                            "  body_source = 'fetched:article', fetched_at = now() "
                            "WHERE id = :id"),
                            {"t": body_txt, "h": body_html, "id": r.id})
            if args.apply:
                db = _commit(db)
            avg_so_far = sum(gained) / len(gained) if gained else 0
            top = ", ".join(f"{k} x{v}" for k, v in
                            sorted(reasons.items(), key=lambda kv: -kv[1])[:3])
            print(f"  [{min(start + BATCH, len(targets)):5}/{len(targets)}] ok {ok}, "
                  f"failed {failed}, avg {avg_so_far:,.0f} chars"
                  + (f"  |  {top}" if top else ""), flush=True)
            time.sleep(args.throttle)

        if args.apply:
            db = _commit(db)
        avg = sum(gained) / len(gained) if gained else 0
        print(f"\n[{'APPLIED' if args.apply else 'DRY-RUN'}] fetched {ok}, failed {failed}; "
              f"average body {avg:,.0f} characters (was {before:,.0f})")

        if args.apply:
            if args.body_code:
                n, avg_now, full = db.execute(text(
                    "SELECT count(*), coalesce(round(avg(nullif(length(body_txt),0))),0), "
                    "       count(*) FILTER (WHERE length(body_txt) >= 1200) "
                    "FROM economy_items WHERE body_code = :code AND item_type = ANY(:types)"),
                    {"code": args.body_code, "types": args.item_type or ["news"]}).fetchone()
            else:
                n, avg_now, full = db.execute(text(
                    "SELECT count(*), coalesce(round(avg(nullif(length(body_txt),0))),0), "
                    "       count(*) FILTER (WHERE length(body_txt) >= 1200) "
                    "FROM eu_news_items WHERE institution = :inst"),
                    {"inst": args.institution}).fetchone()
            print(f"[VERIFY] {label}: {n} row(s), average {int(avg_now):,} chars, "
                  f"{full} of document length")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
