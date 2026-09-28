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
    # op.europa.eu publication-detail portlets (dpp/jrc_report)
    "web content display",
    "for a better user experience",
)


def visible_text(fragment: str) -> str:
    stripped = _STRIP_TAGS.sub(" ", fragment)
    text = html_lib.unescape(re.sub(r"(?s)<[^>]+>", " ", stripped))
    return re.sub(r"\s+", " ", text).strip()


# Leading punctuation a close button or icon leaves behind. EUR-Lex opens its pages with
# "\u00d7 Skip to main content", and `startswith` missed it by exactly one character, so
# 3,178 characters of portal navigation read as an article.
# A leading "." is how a rendered cookie banner arrives (". Visit our cookies
# policy page..."), and it blocked every furniture token from matching. No
# article opens with a bare period or comma, so skipping them is safe.
_LEADING_JUNK = re.compile(r"^[\s\u00d7\u2715\u2716xX*\u2022\-\u2013\u2014|>\]\[.,]+")


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
    # A WAF REJECTION is not a challenge you can pass and not a document. The JRC Product
    # Bureau answers 244 bytes of "The requested URL was rejected. Please consult with your
    # administrator. Your support ID is: <...>" (BIG-IP ASM). It carries no consent banner,
    # no navigation and no listing markers, so every other guard waved it through, and the
    # fetcher was about to store it as a 123-character body for a textiles DPP study.
    re.compile(r"(?i)the requested url was rejected"),
    re.compile(r"(?i)your support id is"),
    re.compile(r"(?i)consult with your administrator"),
    re.compile(r"(?i)\breference\s*#\s*[0-9a-f]{8,}"),
    re.compile(r"(?i)access to this page has been denied"),
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

# Site navigation labels. These are NOT in the list above, because each is a phrase a real
# sentence can open with: stripping "what we do" unconditionally turned "What we do in this
# report is assess the maritime domain" into "in this report is assess...". A nav BAR is a
# RUN of them; a sentence starts with at most one. So a token here is only removed when at
# least two appear back to back.
_NAV_RUN_TOKENS = (
    "news and events", "what we do", "who we are", "publications & data",
    "careers", "procurement", "portals",          # EDA
    "home", "about us", "contact", "search", "menu",
    # Europa cookie banner, which the rendered page carries before anything else.
    "visit our cookies policy page or click the link in any footer for more information"
    " and to change your preferences.",
    "accept all cookies", "accept only essential cookies", "we use cookies",
    # EU Funding & Tenders Portal, whose Angular shell renders its whole left nav ahead
    # of the article. All multi-word but for the two that cannot begin a sentence here;
    # a run of two is still required, so "Funding for X" is never truncated.
    "eu funding & tenders portal", "sign in", "calls for proposals",
    "participant register", "projects & results", "eu funded projects",
    "results & innovation support", "programme dashboards", "news & events",
    "work as an expert", "guidance & documents", "guidance & manuals",
    "reference documents", "how to participate", "faqs", "helpdesk & support",
    "sme self-assessment tool", "videos", "sedia.global.news",
)
_MIN_NAV_RUN = 2


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
            return _strip_nav_run(stripped).strip()
        out = stripped
    return _strip_nav_run(out).strip()


def _strip_nav_run(text: str) -> str:
    """Remove a leading RUN of navigation labels, never a single one."""
    cursor, matched = text, 0
    while matched < 12:
        probe = _LEADING_JUNK.sub("", cursor)
        lowered = probe.lower()
        for token in _NAV_RUN_TOKENS:
            if lowered.startswith(token):
                cursor, matched = probe[len(token):], matched + 1
                break
        else:
            break
    # Fewer than the minimum means this was prose, not a nav bar: leave the text untouched.
    return cursor if matched >= _MIN_NAV_RUN else text


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
