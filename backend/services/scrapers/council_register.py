"""Council of the EU document register — the real documents behind
`/api/v1/council-documents`.

Why this exists (D1, 27 Aug 2026)
---------------------------------
`/api/v1/council-documents` is described as *"Council documents — press releases,
conclusions, meeting agendas, summits"*. It unions two branches:

    1. institutional_publications, Council-tagged  -> 0 rows. Empty since it shipped.
    2. eu_calendar_events, institution=COUNCIL     -> 61 rows.

So every row it has ever returned is a MEETING. It is an events feed wearing a
documents name, and the failure is silent and inverted: `?q=minors` returns 200
with an empty list, and a caller concludes the Council has said nothing about
minors online. The Council has: 25 EU Member States and 2 EFTA countries signed
the **Jutland Declaration, Shaping a Safe Online World for Minors**, at the
informal Telecommunications Council in Horsens on 9-10 October 2025 (recorded in
Council document ST 15875/25, TELECOM 427, 27 November 2025).

This module fills branch 1 with real Council documents.

What was measured before writing it
-----------------------------------
* `www.consilium.europa.eu` answers an honest bot UA with **403** behind a browser
  check, so it needs Playwright (`feedback_waf_walled_use_playwright`).
* `data.consilium.europa.eu` is **NOT** walled: a plain curl of
  `/doc/document/ST-15875-2025-INIT/en/pdf` returns 200. Document FETCHING is
  therefore cheap; only the register SEARCH needs a browser.
* The search parameters were READ OFF THE FORM, not guessed. They are:
  `query`, `WordsInSubject`, `WordsInText`, `DocumentNumber`,
  `InterinstitutionalFiles`, `SubjectMatters`, `DocumentTypes`,
  `DateFrom`, `DateTo`, `MeetingDateFrom`, `MeetingDateTo`, `DocumentLanguage`,
  `OrderBy`, and `page`.

A correction worth keeping, because it nearly shaped this module wrongly
--------------------------------------------------------------------
The first version of this file recorded that the register was "queryable but not
enumerable", on the evidence that a date-range search returned nothing. That was
false. The query used `DocumentDateFrom` / `DocumentDateTo`, which the form does
not have; the real names are `DateFrom` / `DateTo`. An undeclared parameter is
silently ignored, so the empty result described MY QUERY, not the register
(`feedback_undeclared_query_param_silently_ignored`,
`feedback_empty_result_is_a_broken_instrument`).

The register IS enumerable by date: `?DateFrom=DD/MM/YYYY&DateTo=DD/MM/YYYY`
returns 20 results a page, paged with `&page=N`, and the result set is capped at
**50 pages (1,000 documents) per window**. Complete coverage of a period is
therefore a matter of choosing windows narrow enough not to hit that cap — and of
SAYING SO when one is hit, rather than returning a truncated page as if complete.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, List, Optional
from urllib.parse import urlencode, urljoin

logger = logging.getLogger(__name__)

REGISTER_SEARCH = (
    "https://www.consilium.europa.eu/en/documents-publications/"
    "public-register/public-register-search/"
)
PRESS_RELEASES = "https://www.consilium.europa.eu/en/press/press-releases/"

# The SEARCH is behind Cloudflare and stays behind it: on 24 September 2026 it answered
# a challenge to plain HTTP, to our own stealth browser at 12s settle, and to Scrape.do
# in plain, render and super modes (502 each, uncharged). Two of the register's own
# listings are NOT walled, and between them they are a real discovery route:
#   * `/latest/` -- the most recent documents (meeting convocations, ~9 at a time);
#   * `/oj-council/` -- provisional agendas, ~169 document links, dated and referenced.
# They are a narrower window than the search, which is why the search failure is still
# reported honestly rather than papered over: a route that finds SOME documents must not
# read as a register that HAS only those documents.
REGISTER_LATEST = "https://www.consilium.europa.eu/en/documents/public-register/latest/"
REGISTER_OJ = "https://www.consilium.europa.eu/en/documents/public-register/oj-council/"

# One result row in the register. Selector confirmed against the live page rather
# than guessed -- `feedback_read_the_producer_not_your_assumption`.
_RESULT_SELECTOR = "li.gsc-public-register__result-item"
_DOC_HREF = re.compile(r"/doc/document/([A-Z]{2}-\d+-\d{4}(?:-[A-Z]+(?:-\d+)?)?)/")
_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
# The result text runs:
#   "<REF> <TYPE> <DD/MM/YYYY> <real title> Subject matters: <codes> Date of ... "
# e.g. "WK 9054 2026 INIT - INFORMATION 22/06/2026 A Cross-Sectoral Approach ..."
# The reference and the document type are stripped OFF the title: a title is what
# a human reads, and Brubru's standing rule keeps institutional codes out of it.
# The stripped pieces are not lost -- the ref becomes `external_id` and the type
# becomes `doc_type`.
_TITLE_CUT = re.compile(r"\s*(Subject matters?:|Date of )", re.I)
# Two stages, because the register's prefix is not one shape.
#   "WK 9054 2026 INIT - INFORMATION 22/06/2026 A Cross-Sectoral ..."
#   "ST 12436 2026 INIT - LEGISLATIVE ACTS AND OTHER INSTRUMENTS: Council Reg ..."
#   "ST 14964 2018 ADD 1 - 'I/A' ITEM NOTE 04/12/2018 Proposal for ..."
# The first version required a DATE after the document type, so the second and
# third forms kept their codes: 35 of 248 stored titles still opened with
# "ST 12436 2026 INIT -". The document type can carry punctuation (' / :) and the
# date is optional, so the reference and the type are stripped separately.
_REF_HEAD = re.compile(
    r"^(?:ST|WK|CM|SN|RE)\s+\d+\s+\d{4}(?:\s+[A-Z]+(?:\s+\d+)?)*\s*-\s*"
)
# An ALL-CAPS document type, optionally quoted or slashed, optionally followed by
# a date. Stops at the first mixed-case word, which is where the human title begins.
_DOCTYPE_HEAD = re.compile(
    r"^(?P<doctype>['\"]?[A-Z][A-Z'\"/\- ]*[A-Z]['\"]?)\s*:?\s*"
    r"(?P<date>\d{2}/\d{2}/\d{4})?\s*"
)


@dataclass
class CouncilDoc:
    external_id: str          # ST-15875-2025-INIT
    title: str
    url: str                  # data.consilium.europa.eu PDF/HTML
    published: Optional[date]
    subject_matters: List[str]
    category: str             # 'document' | 'press_release'
    doc_type: Optional[str] = None   # NOTE | WORKING DOCUMENT | INFORMATION | ...

    def as_row(self) -> dict:
        return {
            "external_id": self.external_id,
            "title": self.title,
            "url": self.url,
            "published": self.published,
            "subject_matters": self.subject_matters,
            "category": self.category,
            "doc_type": self.doc_type,
        }


def _fetch_rendered(url: str) -> str:
    """Render a WAF-walled consilium page with Playwright and return its HTML.

    Raises rather than returning "" on failure: a caller must not be able to read
    a fetch error as an empty register. `feedback_empty_result_is_a_broken_instrument`.
    """
    from services.scrapers.waf_browser_fetcher import fetch_one

    res = fetch_one(url, expand_accordions=False, strip_chrome=False)
    html = getattr(res, "html", None) or ""
    if len(html) < 500:
        raise RuntimeError(
            f"consilium render returned {len(html)} bytes for {url} -- treat as a "
            "FETCH FAILURE, never as 'no documents'"
        )
    # A size guard is not a content guard (measured 22 September 2026).
    #
    # The register had gone quiet: `ingest_council_documents.py --since-days 30`
    # inserted 0 and the corpus had not moved since 27 August, through a month
    # that contained a General Affairs Council. The size check passed, because
    # what came back was ~15,000 bytes of Cloudflare interstitial whose entire
    # visible text is "Just a moment... Checking your browser before accessing a
    # GSC Managed Website ... Enable JavaScript and cookies to continue".
    # `_parse_results` then found no result items and returned [], and the run
    # logged "0 document(s)" -- a hard block reported as an empty register.
    #
    # Raising longer settle times does not help: tested at 6s and 15s, the
    # challenge page comes back byte-identical. So this is a genuine block to be
    # reported, not a timing problem to be tuned around.
    lowered = html[:4000].lower()
    if any(m in lowered for m in (
        "just a moment", "checking your browser", "enable javascript and cookies",
        "cf-browser-verification", "attention required! | cloudflare",
    )):
        raise RuntimeError(
            f"consilium returned a BROWSER-CHALLENGE page for {url} "
            f"({len(html)} bytes, no results markup) -- this is a FETCH BLOCK. "
            "Never record it as 'no documents'."
        )
    return html


def _parse_results(html: str) -> List[CouncilDoc]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    out: List[CouncilDoc] = []
    seen: set[str] = set()

    for li in soup.select(_RESULT_SELECTOR):
        link = li.find("a", href=_DOC_HREF)
        if not link:
            continue
        m = _DOC_HREF.search(link["href"])
        if not m:
            continue
        ext_id = m.group(1)
        # A document appears once per language/format; keep the first.
        if ext_id in seen:
            continue

        text = " ".join(li.get_text(" ", strip=True).split())
        cut = _TITLE_CUT.search(text)
        head = (text[: cut.start()] if cut else text).strip()

        doc_type, prefix_date = None, None
        m_ref = _REF_HEAD.match(head)
        if m_ref:
            head = head[m_ref.end():]
            m_type = _DOCTYPE_HEAD.match(head)
            if m_type and len(m_type.group("doctype")) > 2:
                doc_type = m_type.group("doctype").strip(" -:'").title()
                prefix_date = m_type.group("date")
                head = head[m_type.end():]
        title = head.strip(" -–—")
        if not title or len(title) < 8:
            continue

        subjects: List[str] = []
        sm = re.search(r"Subject matters?:\s*([A-Z ,]+?)(?:\s+Date of|\s*$)", text)
        if sm:
            subjects = [s.strip() for s in sm.group(1).split(",") if s.strip()]

        # Prefer the DOCUMENT date from the reference prefix over any later date
        # in the row, which is the date of the MEETING the document went to.
        published = None
        d = _DATE_RE.search(prefix_date) if prefix_date else _DATE_RE.search(text)
        if d:
            try:
                published = date(int(d.group(3)), int(d.group(2)), int(d.group(1)))
            except ValueError:
                published = None

        seen.add(ext_id)
        out.append(CouncilDoc(
            external_id=ext_id,
            title=title,
            url=urljoin("https://data.consilium.europa.eu",
                        f"/doc/document/{ext_id}/en/pdf"),
            published=published,
            subject_matters=subjects,
            category="document",
            doc_type=doc_type,
        ))
    return out


def _parse_listing(html: str, category: str = "document") -> List[CouncilDoc]:
    """Documents out of a register LISTING page (`/latest/`, `/oj-council/`).

    A listing is not the search: there is one row per document with its own PDF links
    in every language, so the same reference appears many times and is kept once, in
    English when English exists. The row's text carries the body that meets, its subject
    codes and the meeting date.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "html.parser")
    by_ref: dict[str, CouncilDoc] = {}
    for a in soup.find_all("a", href=True):
        m = _DOC_HREF.search(a["href"])
        if not m:
            continue
        ref = m.group(1)
        lang = a["href"].rsplit("/", 2)[-2] if a["href"].count("/") >= 2 else ""
        row = a.find_parent(["li", "tr", "article", "div"])
        text = row.get_text(" ", strip=True) if row else a.get_text(" ", strip=True)
        dm = _DATE_RE.search(text)
        published = None
        if dm:
            try:
                published = date(int(dm.group(3)), int(dm.group(2)), int(dm.group(1)))
            except ValueError:
                published = None
        subjects: List[str] = []
        if "Subject matters" in text:
            tail = text.split("Subject matters", 1)[1].lstrip(": ")
            subjects = [c.strip() for c in _TITLE_CUT.split(tail)[0].split(",") if c.strip()][:12]
        title = _TITLE_CUT.split(text)[0].strip()
        title = _REF_HEAD.sub("", title).strip() or ref
        # One row links its document in every official language. Keep one per
        # reference, and prefer English when a later link offers it.
        prev = by_ref.get(ref)
        if prev is not None and not (lang == "en" and not prev.url.endswith("/en/pdf")):
            continue
        if prev is not None:
            prev.url = a["href"] if a["href"].startswith("http") else f"https://data.consilium.europa.eu{a['href']}"
            continue
        by_ref[ref] = CouncilDoc(
            external_id=ref,
            title=title[:480],
            url=a["href"] if a["href"].startswith("http") else f"https://data.consilium.europa.eu{a['href']}",
            published=published,
            subject_matters=subjects,
            category=category,
            doc_type=None,
        )
    return list(by_ref.values())


def fetch_register_listings(include_agendas: bool = True) -> tuple[List[CouncilDoc], List[str]]:
    """The register's unwalled listings, and which of them failed.

    The search is blocked (see REGISTER_LATEST / REGISTER_OJ above), so this is the
    discovery route that still works. It returns what it found AND the sources that
    did not answer, because "9 documents" and "9 documents, and the agendas page was
    down" are different facts and the caller must be able to tell them apart.
    """
    found: dict[str, CouncilDoc] = {}
    failed: List[str] = []
    targets = [("latest", REGISTER_LATEST)]
    if include_agendas:
        targets.append(("oj-council", REGISTER_OJ))
    for label, url in targets:
        try:
            for doc in _parse_listing(_fetch_rendered(url)):
                found.setdefault(doc.external_id, doc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[council-register] listing %s unavailable: %s", label, exc)
            failed.append(f"{label}: {type(exc).__name__}")
    return list(found.values()), failed


PAGE_SIZE = 20
MAX_PAGES = 50          # the register's own ceiling: 50 pages == 1,000 documents


def _search(params: dict, label: str, max_pages: int) -> tuple[List[CouncilDoc], bool]:
    """Walk `&page=N` until a page yields nothing new.

    Returns (docs, truncated). `truncated` is True when the walk stopped because
    it hit the register's 1,000-document ceiling rather than because it ran out
    of results -- the caller MUST surface that, or a capped window reads as a
    complete one. This is the `all_items[:20]` mistake in a different costume.
    """
    docs: List[CouncilDoc] = []
    seen: set[str] = set()
    truncated = False

    for page in range(1, max_pages + 1):
        qs = urlencode({**params, "page": page}) if page > 1 else urlencode(params)
        batch = _parse_results(_fetch_rendered(f"{REGISTER_SEARCH}?{qs}"))
        fresh = [d for d in batch if d.external_id not in seen]
        if not fresh:
            break
        for d in fresh:
            seen.add(d.external_id)
        docs.extend(fresh)
        if len(batch) < PAGE_SIZE:
            break          # a short page is the last page
        if page == max_pages:
            truncated = True

    logger.info("[council-register] %-34s -> %4d document(s)%s",
                label, len(docs), "  [TRUNCATED at the register cap]" if truncated else "")
    return docs, truncated


def search_register(term: str, date_from: Optional[date] = None,
                    max_pages: int = 5) -> List[CouncilDoc]:
    """Targeted search by words in the document SUBJECT.

    Kept for backfilling a known gap (e.g. `minors`). Breadth comes from
    `search_by_date`, which enumerates rather than guessing vocabulary.
    """
    params = {"WordsInSubject": term}
    if date_from:
        params["DateFrom"] = date_from.strftime("%d/%m/%Y")
    docs, _ = _search(params, f"subject:{term}", max_pages)
    return docs


def search_full_text(term: str, date_from: Optional[date] = None,
                     max_pages: int = 5) -> List[CouncilDoc]:
    """Search the document TEXT, not just the subject line.

    Wider recall than `search_register`: a document about protecting minors may
    carry a bureaucratic subject line and say so only in the body.
    """
    params = {"WordsInText": term}
    if date_from:
        params["DateFrom"] = date_from.strftime("%d/%m/%Y")
    docs, _ = _search(params, f"text:{term}", max_pages)
    return docs


def search_by_date(date_from: date, date_to: date,
                   max_pages: int = MAX_PAGES) -> tuple[List[CouncilDoc], bool]:
    """Enumerate every register document in a date window.

    This is the breadth mechanism. The register caps a result set at 1,000
    documents, so a window wide enough to exceed that comes back truncated and
    says so through the second return value.
    """
    params = {
        "DateFrom": date_from.strftime("%d/%m/%Y"),
        "DateTo": date_to.strftime("%d/%m/%Y"),
    }
    return _search(params, f"{date_from} .. {date_to}", max_pages)


def fetch_press_releases() -> List[CouncilDoc]:
    """Council press releases.

    The publication date lives in the article PATH
    (/en/press/press-releases/YYYY/MM/DD/slug), which is more reliable than any
    on-page string -- the same reasoning as `scrape_eu_news.scrape_waf_listing`.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(_fetch_rendered(PRESS_RELEASES), "html.parser")
    href_re = re.compile(r"/en/press/press-releases/(\d{4})/(\d{2})/(\d{2})/([^/?#]+)")
    out: List[CouncilDoc] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        m = href_re.search(a["href"])
        if not m:
            continue
        title = " ".join(a.get_text(" ", strip=True).split())
        if not title or len(title) < 15:
            continue
        url = urljoin(PRESS_RELEASES, a["href"])
        if url in seen:
            continue
        seen.add(url)
        try:
            published = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            published = None
        out.append(CouncilDoc(
            # Stable across runs: the dated slug is the document's identity.
            external_id=f"PR-{m.group(1)}{m.group(2)}{m.group(3)}-{m.group(4)[:80]}",
            title=title,
            url=url,
            published=published,
            subject_matters=[],
            category="press_release",
        ))
    logger.info("[council-register] press releases -> %d item(s)", len(out))
    return out


# ---------------------------------------------------------------------------
# Document text
# ---------------------------------------------------------------------------
# `data.consilium.europa.eu` is NOT behind the browser check that guards
# `www.consilium.europa.eu`, so the document itself is a plain HTTP fetch. No
# Playwright, no WAF dance -- measured, not assumed.
#
# The text matters for more than completeness. `/api/v1/council-documents`
# promises `body_txt` in its 5-datapoint contract, and its `q` filter is useless
# without it: the register documents that discuss protecting minors online carry
# subject lines like "ANNEX to the COUNCIL IMPLEMENTING DECISION amending ...".
# Searching titles alone finds none of them, which is how a real corpus can still
# answer "nothing" to a real question.

_UA = "Brubru/1.0 (+https://brubru.beresol.eu)"
_TEXT_TIMEOUT = 30


def fetch_document_text(doc: "CouncilDoc", max_chars: int = 200_000) -> Optional[str]:
    """Plain-text body of a register document, or None if it cannot be read.

    Returns None rather than "" on failure so the caller can tell "no body" from
    "empty body" and does not persist an empty string as if it were the document.
    """
    import requests

    # `www.consilium.europa.eu` sits behind the browser check; `data.consilium`
    # does not. A press release therefore CANNOT be read with plain requests --
    # measured: it returns nothing, and the first version of this function
    # reported "no body" for all 17 press releases as though they had none.
    if "//www.consilium.europa.eu" in doc.url:
        try:
            from services.scrapers.waf_browser_fetcher import fetch_one
            from bs4 import BeautifulSoup

            res = fetch_one(doc.url, expand_accordions=False, strip_chrome=True)
            html = getattr(res, "html", None) or ""
            if len(html) < 500:
                logger.debug("[council-register] %s rendered %d bytes",
                             doc.external_id, len(html))
                return None
            soup = BeautifulSoup(html, "html.parser")
            for junk in soup(["script", "style", "noscript", "nav", "header", "footer"]):
                junk.decompose()
            # Strip the consent banner explicitly. Without this the stored body
            # OPENS with "We use cookies to improve you..." -- 590 characters of
            # chrome that a length check happily accepts as a document.
            for junk in soup.select(
                "[class*=cookie], [class*=consent], [class*=banner]"
            ):
                junk.decompose()
            # The article itself, not the whole page.
            main = soup.select_one("main.gsc-main-content") or soup.select_one("main")
            body = " ".join((main or soup).get_text(" ", strip=True).split())
            return body[:max_chars] if len(body) > 200 else None
        except Exception as exc:  # noqa: BLE001
            logger.debug("[council-register] browser body %s failed: %s",
                         doc.external_id, exc)
            return None

    try:
        r = requests.get(doc.url, headers={"User-Agent": _UA}, timeout=_TEXT_TIMEOUT)
        if r.status_code != 200 or not r.content:
            logger.debug("[council-register] %s -> HTTP %s", doc.external_id, r.status_code)
            return None

        if doc.url.endswith("/pdf") or r.content[:4] == b"%PDF":
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(r.content))
            text = "\n".join((p.extract_text() or "") for p in reader.pages)
        else:
            from bs4 import BeautifulSoup
            text = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)

        text = " ".join(text.split())
        return text[:max_chars] if text.strip() else None
    except Exception as exc:  # noqa: BLE001
        logger.debug("[council-register] body %s failed: %s", doc.external_id, exc)
        return None


_SUBJECT_RE = re.compile(r"Subject\s*:\s*(.+?)(?:\n\s*\n|$)", re.S)


def fetch_by_reference(ref: str) -> Optional["CouncilDoc"]:
    """Build a CouncilDoc from a known register reference, e.g. ST-15875-2025-INIT.

    `data.consilium.europa.eu` serves any document by reference over plain HTTP,
    so a document you can NAME can always be ingested -- no register search, no
    browser, no dependence on a search term happening to surface it.

    This exists because the search did not surface ST-15875-2025-INIT (the record
    of the Jutland Declaration) within its page budget, and "the search did not
    return it" is not a good reason for a known Council document to be absent
    from a Council documents endpoint.

    The title comes from the document's own `Subject:` header rather than from a
    listing page, which makes it the primary source for its own metadata.
    """
    ref = ref.strip().upper().replace(" ", "-")
    url = f"https://data.consilium.europa.eu/doc/document/{ref}/en/pdf"
    probe = CouncilDoc(external_id=ref, title=ref, url=url, published=None,
                       subject_matters=[], category="document")
    text_body = fetch_document_text(probe)
    if not text_body:
        logger.warning("[council-register] %s unreadable at %s", ref, url)
        return None

    title = ref
    m = _SUBJECT_RE.search(text_body[:4000])
    if m:
        title = " ".join(m.group(1).split())[:400]

    published = None
    d = re.search(r"Brussels,\s+(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})", text_body[:2000])
    if d:
        try:
            published = datetime.strptime(
                f"{d.group(1)} {d.group(2)} {d.group(3)}", "%d %B %Y").date()
        except ValueError:
            published = None

    probe.title = title
    probe.published = published
    return probe
