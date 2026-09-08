"""
European Ombudsman (api_eesc_cor_ombud.md). /api/v2/ombudsman.

ombudsman.europa.eu is a single-page app: the listing and about pages render their
content client-side, so the Ombudsman is read through Playwright. Source map
(verified 25 Jun 2026):
  - news  : /news-documents — rendered links to /news-document/<id>, each prefixed
            with a category label ("Latest news or press release", "Press release",
            "Speech", ...) that is stripped from the title.
  - topic : the about, strategy, how-we-work, areas-of-work, impact, complaints,
            inquiries-overview and publications pages.

The European Ombudsman investigates complaints of maladministration in the EU
institutions and bodies. Reads from economy_items (body row seeded by migration
171); 5 mandatory datapoints. Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, norm_url, extract_html, error_body_reason

_BASE = "https://www.ombudsman.europa.eu"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")

NEWS_PAGE = f"{_BASE}/news-documents"

# Canonicalise a news-document URL to the form the SITE ITSELF declares canonical.
#
# Why (measured 8 September 2026)
# -------------------------------
# The SPA listing emits 11 hrefs for 10 distinct items: ten as
# `/en/news-document/en/<id>` and one as `/news-document/en/<id>`. The old `seen`
# set deduped on the URL STRING, so the odd form survived as a SECOND row for an
# item already collected. Over successive runs different ids came out in the odd
# form, which is how 21 rows accumulated for 16 real items -- and the two rows
# disagreed on content, because one render succeeded and the other did not
# (bodies of 3,642 vs 203 chars, and 6 rows with body_txt NULL).
#
# Which form is canonical is not a guess: BOTH variants serve
#   <link rel="canonical" href="https://www.ombudsman.europa.eu/en/news-document/en/<id>">
# so the site says the /en/-prefixed form is the one. Dedup on the numeric id and
# store that form.
# Only the LEADING LOCALE PREFIX differs between the two variants; the segment after
# `news-document/` is the DOCUMENT's language and must be preserved. Collapsing that
# too would map /news-document/fr/231701 onto the English URL and silently claim a
# French document was the English one.
_NEWS_ID_RE = re.compile(r"/news-document/([a-z]{2})/(\d+)\b")


def canonical_news_url(href: str) -> tuple[str, str] | tuple[None, None]:
    """(canonical_url, dedup_key) for a news-document href, or (None, None).

    Adds the `/en/` locale prefix the site declares canonical and keeps the
    document-language segment untouched. The dedup key is (lang, id), so the same
    item in two languages stays two items while the same item under two locale
    prefixes collapses to one.
    """
    m = _NEWS_ID_RE.search(href or "")
    if not m:
        return None, None
    doc_lang, item_id = m.group(1), m.group(2)
    return f"{_BASE}/en/news-document/{doc_lang}/{item_id}", f"{doc_lang}:{item_id}"

_TOPIC_PATHS = [
    "/the-ombudsman",
    "/our-strategy/strategy",
    "/history",
    "/how-we-work",
    "/areas-of-work",
    "/impact",
    "/legal-basis/treaties",
    "/european-network-of-ombudsmen/about",
    "/make-a-complaint",
    "/strategic-issues/strategic-inquiries/all-strategic-inquiries",
    "/top-inquiries",
    "/publications",
]

# The SPA wraps every page -- good ones and error ones -- in this persistent
# navigation. A body consisting of nothing BUT the wrapper is a render that never
# settled, not content: row 643471 held 109 chars of exactly this and passed the
# shared `error_body_reason` floor. Site-specific, so it lives here rather than in
# economy_common: the generic guard must not reject legitimately short notices.
_CHROME_FRAGMENTS = (
    "You have a complaint",
    "against an EU institution or body?",
    "Make a complaint",
    "Contents",
    "Short link",
    "Export",
    "Subscribe to the case",
    "Get notified by email when the case is updated",
    "Get notified by RSS when the case",
    "Take Me Home",
    "Contact technical support",
)
_CHROME_MIN_REMAINDER = 120   # chars of non-boilerplate needed to count as content


def chrome_only_reason(body_txt: str | None) -> str | None:
    """'chrome_only' when stripping the site wrapper leaves almost nothing."""
    if not body_txt:
        return None
    remainder = body_txt
    for frag in _CHROME_FRAGMENTS:
        remainder = remainder.replace(frag, " ")
    remainder = " ".join(remainder.split())
    if len(remainder) < _CHROME_MIN_REMAINDER:
        return f"chrome_only(remainder={len(remainder)})"
    return None


_CATEGORY_PREFIX = re.compile(
    r"^(Latest news or press release|Press release|News article|News|Speech|"
    r"Document|Publication|Featured story|Decision|Report|Letter)\s+", re.I)


async def _render(page, url: str, settle: int = 2800) -> str | None:
    try:
        resp = await page.goto(url, wait_until="networkidle", timeout=55000)
        await page.wait_for_timeout(settle)
    except Exception:
        return None
    if resp is None or resp.status != 200:
        return None
    return await page.content()


async def _ingest_news_async(*, fetch_bodies: bool) -> list[Item]:
    from playwright.async_api import async_playwright
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        html = await _render(page, NEWS_PAGE)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.select('a[href*="/news-document/"]'):
                url, dedup_key = canonical_news_url(a.get("href", ""))
                if url is None:
                    continue
                # Dedup on the item ID, not the URL string. The listing emits the
                # same item under two locale-prefix variants; string dedup let both
                # through and created a duplicate row with disagreeing content.
                if dedup_key in seen:
                    continue
                raw = clean(a.get_text(" ", strip=True))
                title = clean(_CATEGORY_PREFIX.sub("", raw))
                if not title or len(title) < 10:
                    continue
                seen.add(dedup_key)
                items.append(Item(body_code="ombudsman", item_type="news", title=title[:300],
                                  public_url=norm_url(url), creation_date=now,
                                  source_kind="html", guid=norm_url(url)))
        if fetch_bodies:
            for it in items:
                dhtml = await _render(page, it.public_url, settle=2000)
                if not dhtml:
                    continue
                body_txt, body_html = extract_html(dhtml)
                # Never store an error page as a body. Before the URL was
                # canonicalised the scraper fetched a non-existent locale variant,
                # got a 404 page, and stored ITS text as body_txt on 4 rows -- which
                # satisfied every "body is not null" check while being false data.
                # Two more rows held unrendered template placeholders. A non-empty
                # body is not a valid body.
                reason = error_body_reason(body_txt) or chrome_only_reason(body_txt)
                if reason:
                    print(f"[ombudsman] discarding body for {it.public_url}: {reason}")
                    continue
                it.body_txt, it.body_html = body_txt, body_html

        # document_date is deliberately left None. Measured 8 September 2026: the
        # CANONICAL rendered item page (76KB) carries none of six date carriers --
        # no <time datetime>, no article:published_time, no JSON-LD datePublished,
        # no parseable visible date. Dates DO appear on the 404 page for the wrong
        # URL variant (103KB), but they belong to its "latest news" sidebar and are
        # other items' dates. Using them would be exactly the fabrication
        # feedback_backfill_no_hallucination forbids, so these rows stay undated and
        # /api/v2/news/all coalesces to creation_date for FILTERING while still
        # reporting document_date as null. /news/latest reports the body as
        # `undated`, which is the honest state.
        await b.close()
    return items


async def _ingest_topics_async(*, fetch_bodies: bool) -> list[Item]:
    from playwright.async_api import async_playwright
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        for path in _TOPIC_PATHS:
            url = _BASE + path
            html = await _render(page, url, settle=2200)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            # The SPA h1 is a fixed "About" banner on every page, so prefer <title>;
            # fall back to a slug-derived title.
            tt = soup.title.get_text(strip=True) if soup.title else ""
            tt = clean(tt.split(" | ")[0].split(" - ")[0])
            slug = clean(path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title())
            title = tt if tt and tt.lower() not in ("about", "european ombudsman", "") else slug
            body_txt, body_html = (extract_html(html) if fetch_bodies else (None, None))
            items.append(Item(body_code="ombudsman", item_type="topic", title=title[:300],
                              public_url=norm_url(url), creation_date=now, source_kind="html",
                              guid=norm_url(url), body_txt=body_txt, body_html=body_html))
        await b.close()
    return items


def ingest_ombudsman_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import asyncio
    return asyncio.run(_ingest_news_async(fetch_bodies=fetch_bodies))


def ingest_ombudsman_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import asyncio
    return asyncio.run(_ingest_topics_async(fetch_bodies=fetch_bodies))
