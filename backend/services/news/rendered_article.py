"""Pull the article out of a JavaScript-rendered Europa page.

Commission DG sites serve an Angular shell: fetched directly they carry 38 characters of
visible text, and the body Brubru stored was composed from the title and summary instead.
Scrape.do renders them, but only with an explicit wait -- without one it returns the same
shell, which is a 200 carrying the failure in its body.

Extraction is deliberately NOT a single selector. The largest `div.ecl-col` block lands
exactly on the article of a DG news page, returns nothing at all on the funding portal, and
returns "Filter by Keywords" on a trade listing page. So: try several containers, score what
each yields, and refuse to store anything that still looks like page furniture.
"""
from __future__ import annotations

import html as html_lib
import re
from typing import Optional

# Enough text to be an article rather than a card or a filter label.
MIN_ARTICLE_CHARS = 400

_STRIP_TAGS = re.compile(
    r"(?is)<(script|style|noscript|nav|header|footer|form|aside|svg)[^>]*>.*?</\1>")

_CONTAINERS = (
    r'(?is)<article[^>]*>(.*?)</article>',
    r'(?is)<main[^>]*>(.*?)</main>',
    r'(?is)<div[^>]*\brole="main"[^>]*>(.*?)</div>',
    r'(?is)<div[^>]*class="[^"]*\becl-col[^"]*"[^>]*>(.*?)</div>',
    r'(?is)<div[^>]*class="[^"]*\bnode__content[^"]*"[^>]*>(.*?)</div>',
    r'(?is)<div[^>]*class="[^"]*\bcontent-block[^"]*"[^>]*>(.*?)</div>',
)

# Page furniture that shows up at the START of a badly-scoped extraction. Matched against
# the opening of the text, never the middle: an article may legitimately discuss cookies.
_CHROME_OPENERS = (
    "this site uses cookies",
    "we use cookies",
    "skip to main content",
    "accept all cookies",
    "filter by keywords",
    "an official website of the european union",
)


def visible_text(fragment: str) -> str:
    stripped = _STRIP_TAGS.sub(" ", fragment)
    text = html_lib.unescape(re.sub(r"(?s)<[^>]+>", " ", stripped))
    return re.sub(r"\s+", " ", text).strip()


# Leading punctuation a close button or icon leaves behind. EUR-Lex opens its pages with
# "\u00d7 Skip to main content", and `startswith` missed it by exactly one character, so
# 3,178 characters of portal navigation read as an article.
_LEADING_JUNK = re.compile(r"^[\s\u00d7\u2715\u2716xX*\u2022\-\u2013\u2014|>\]\[]+")


def looks_like_chrome(text: str) -> bool:
    """True when the text opens with navigation or consent furniture."""
    head = _LEADING_JUNK.sub("", text[:200]).lower()
    return any(head.startswith(opener) for opener in _CHROME_OPENERS)


# A listing page is not an article. The trade site's /news_en rendered 3,053 characters of
# index -- "Showing results 1 to 10", ten headlines and their dates -- which scored well on
# length and opened with no consent banner. Stored as a body it would read as a real article
# about ten unrelated things.
_LISTING_MARKERS = (
    re.compile(r"(?i)showing\s+results?\s+\d+\s+to\s+\d+"),
    re.compile(r"(?i)\bfilter by\b"),
    re.compile(r"(?i)\bsort by\b.{0,40}\brelevance\b"),
    re.compile(r"(?i)\bresults? per page\b"),
)
# Repeated item furniture: one article says "News article" once at most; an index repeats it.
_ITEM_STAMP = re.compile(r"(?i)\b(news article|press release|read more)\b")


def looks_like_listing(text: str) -> bool:
    if any(m.search(text[:600]) for m in _LISTING_MARKERS):
        return True
    return len(_ITEM_STAMP.findall(text)) >= 4


# A challenge page is not an article. Cedefop answers HTTP 200 with "Due to unusually high
# traffic, we need to verify that requests are coming from real users" and an arithmetic
# puzzle; 502 economy rows and 50 news rows were storing that text as the body of an article,
# and serving it. Detected and refused here -- never solved, and never stored.
_CHALLENGE_MARKERS = (
    re.compile(r"(?i)unusually high traffic"),
    re.compile(r"(?i)verify that requests are coming from real users"),
    re.compile(r"(?i)complete the verification below"),
    re.compile(r"(?i)checking your browser before accessing"),
    re.compile(r"(?i)enable javascript and cookies to continue"),
    re.compile(r"(?i)please prove you are human"),
    re.compile(r"(?i)\bcf-browser-verification\b|\bcf_chl_\w+"),
    re.compile(r"(?i)access denied.{0,40}(reference|ray) (id|number)"),
)


def looks_like_challenge(text: str) -> bool:
    """True when the page is a bot check rather than the document."""
    if not text:
        return False
    head = text[:1500]
    return any(marker.search(head) for marker in _CHALLENGE_MARKERS)


# Phrases a page opens with before its article starts. EU-OSHA pages read "Skip to main
# content Highlights Back to highlights 14/12/2025 <the actual highlight>": furniture FOLLOWED
# by a real article. Refusing those would throw away 110 genuine bodies, and storing them
# whole puts navigation into the text a partner searches. So: strip the run, then judge what
# is left.
_STRIPPABLE_OPENERS = (
    "skip to main content", "skip to content", "skip to search", "skip to navigation",
    "back to highlights", "back to events", "back to news", "highlights", "osh events",
    "accept all cookies", "accept only essential cookies", "refuse", "accept",
    "this site uses cookies", "we use cookies",
)


def strip_page_furniture(text: str) -> str:
    """Remove the run of navigation phrases a page opens with. Keeps the article."""
    if not text:
        return text
    out = text
    for _ in range(12):  # bounded: a page opens with a handful of these, not hundreds
        stripped = _LEADING_JUNK.sub("", out)
        lowered = stripped.lower()
        for opener in _STRIPPABLE_OPENERS:
            if lowered.startswith(opener):
                stripped = stripped[len(opener):]
                break
        else:
            return stripped.strip()
        out = stripped
    return out.strip()


def is_app_shell(page_html: str) -> bool:
    """A rendered page that never ran: the Angular root is present and empty of prose."""
    return "<app-root" in page_html.lower() and len(visible_text(page_html)) < 200


def extract_article(page_html: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """(text, html, reason). Reason is set only when nothing usable was found."""
    if not page_html:
        return None, None, "empty response"
    if is_app_shell(page_html):
        return None, None, "app shell: the page did not render"
    if looks_like_challenge(visible_text(page_html)):
        return None, None, "bot challenge, not the document: back off and retry later"

    best_text, best_html = "", ""
    for pattern in _CONTAINERS:
        for fragment in re.findall(pattern, page_html):
            text = visible_text(fragment)
            if (len(text) <= len(best_text) or looks_like_chrome(text)
                    or looks_like_listing(text) or looks_like_challenge(text)):
                continue
            best_text, best_html = text, fragment

    if not best_text:
        return None, None, "no article container matched (or every match was chrome or a listing)"
    if len(best_text) < MIN_ARTICLE_CHARS:
        return None, None, f"only {len(best_text)} characters: a card, not an article"
    return best_text, best_html, None
