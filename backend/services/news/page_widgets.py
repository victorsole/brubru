"""Share buttons, newsletter links and scripts are not part of an article (16 Oct 2026).

509 of 512 Parliament press releases on /api/v2/news/all carried "Share this page:
Facebook X LinkedIn WhatsApp ... Sign up for mail updates PDF version" in body_txt and the
share widget, with its tracking links, in body_html; EMA, EPPO, ERCEA, ENISA and ECDC bodies
the same; 167 body_html held <script> or onclick. The page readers strip these before
storing, and the stored rows were cleaned with the same two functions.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

_WIDGET_CLASS = re.compile(r"(?:^|[\s_-])(?:share|sharing|social|socialnetwo|addtoany|sharethis|ep_links)"
                           r"(?:$|[\s_-])|^ep-a_share|^ep_share|^ecl-social-media", re.I)
_SHARE_HREF = re.compile(r"facebook\.com/shar|x\.com/intent|twitter\.com/(?:intent|share)|linkedin\.com/share"
                         r"|api\.whatsapp\.com/send|wa\.me/|mailto:\?|bsky\.app/intent|reddit\.com/submit", re.I)
_ON_ATTR = re.compile(r"^on[a-z]+$", re.I)
# A block of OTHER items under the article, by class or id: the Committee of the Regions'
# field--name-extra-field-newsroom-item-related-news, EEAS field--name-field-related-stories,
# EESC block-eesc-foundation-views-block-recommendation ("Recommended for you"), the
# Commission's block-ewcms-theme-morenewsonasimilartopic... Related documents and links stay.
_RELATED_CLASS = re.compile(r"related[-_](?:news|articles?|stories|press)|views-block-recommendation"
                            r"|morenewsonasimilartopic", re.I)

# Lines a share widget leaves in the text, and a relative time ("6 hours ago") that is
# wrong the moment it is stored.
_CHROME_LINE = re.compile(
    r"^(?:share this(?: page| article)?\s*:?|share on (?:facebook|x|linkedin|whatsapp)|facebook|x|twitter|linkedin|"
    r"whatsapp|e-?mail|bluesky|mastodon|youtube|instagram|threads|pinterest|reddit|tumblr|other networks|share|"
    r"gmail|typepad|blogger|pocket|yahoomail|weibo|viadeo|qzone|netvibes|yammer|digg|messenger|"
    r"follow us on(?: [a-z]+)?|sign up for mail updates|pdf version|print|copy link|"
    r"\d+\s+(?:seconds?|minutes?|hours?|days?)\s+ago)$", re.I)


# A list of other items under the article, by its heading (EU-OSHA's highlights end in
# "Related publications": eight cards, each "Read more"). "Related events" is not here:
# the EESC uses it for the plenary that adopted THIS opinion, and its list of other items
# starts at "Recommended for you".
_RELATED_START = re.compile(r"^(?:related (?:news|articles|stories|press releases|publications)|recommended for you|"
                            r"you (?:may|might) also (?:like|be interested in))\s*:?$", re.I)
_ITEM_DATE = re.compile(r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4}\b"
                        r"|\b\d{1,2}[./]\d{1,2}[./]\d{4}\b", re.I)


def _drop_related_blocks(soup) -> int:
    """Remove the blocks of other items (see _RELATED_CLASS and _RELATED_START). Without a
    known class or id, the block is the largest element that BEGINS with a "Related news" /
    "Recommended for you" heading and lists at least two dates (ELA, an EEAS campaign page)."""
    removed = 0
    for tag in soup.find_all(class_=_RELATED_CLASS) + soup.find_all(id=_RELATED_CLASS):
        if not tag.decomposed:
            tag.decompose()
            removed += 1
    heads = soup.find_all(string=lambda x: x and _RELATED_START.match(x.strip()))
    page_len = len(soup.get_text(" ", strip=True)) if heads else 0
    for head in heads:
        if getattr(head, "parent", None) is None or head.parent.decomposed:
            continue
        block, node = None, head.parent
        while node is not None and node.name not in ("main", "article", "body", "[document]"):
            text = node.get_text("\n", strip=True)
            if not text.startswith(head.strip()):
                break
            if len(_ITEM_DATE.findall(text)) >= 2:
                block = node
            node = node.parent
        # Never more than half the page: a wrapper that begins with a sidebar list can also
        # hold the article.
        if block is not None and len(block.get_text(" ", strip=True)) <= page_len / 2:
            block.decompose()
            removed += 1
    return removed


def clean_html(html: str | None) -> str | None:
    """The same HTML without share widgets, scripts, styles and on* handlers."""
    if not html or not isinstance(html, str):
        return html
    soup = BeautifulSoup(html, "html.parser")
    removed = 0
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
        removed += 1
    for tag in soup.find_all(class_=_WIDGET_CLASS):
        tag.decompose()
        removed += 1
    removed += _drop_related_blocks(soup)
    for a in soup.find_all("a", href=_SHARE_HREF):
        (a.find_parent("li") or a).decompose()
        removed += 1
    for tag in soup.find_all(True):
        for attr in [k for k in tag.attrs if _ON_ATTR.match(k)]:
            del tag.attrs[attr]
            removed += 1
    # Nothing removed: the stored HTML as it was, not a re-serialised copy.
    return str(soup) if removed else html


_MENU_START = re.compile(r"^(?:participating member states|follow us|subscribe to our newsletter|newsletter|"
                         r"related links|quick links|useful links)\s*:?$", re.I)


def _cut_trailing_menu(lines: list[str]) -> list[str]:
    """Drop a site menu stored after the article: from a "Follow us" / "Subscribe to our
    newsletter" line, when what follows is a run of short menu entries ("News and Events",
    "Latest News", "Events", ...; EDA, 16 Oct 2026). Only in the last two thirds of the text,
    and only when at least 6 of the next 8 lines are short."""
    start = len(lines) // 3
    for i in range(start, len(lines)):
        if _MENU_START.match(lines[i].strip()):
            nxt = [ln.strip() for ln in lines[i + 1:i + 9] if ln.strip()]
            if len(nxt) >= 6 and sum(len(x) <= 40 for x in nxt) >= 6:
                return lines[:i]
    return lines


def _cut_related_list(lines: list[str]) -> list[str]:
    """Drop the list of OTHER items a page shows under its article: from a "Related news" /
    "Recommended for you" line, when at least two short date lines follow (each listed item
    carries its date). Only in the last two thirds of the text.

    18 Oct 2026: the CoR's article pages end in three other news items, each stamped
    "Press release", which made the page read as a listing, so 6 CoR articles were stored
    as nothing; where an article was stored, its "Related news" came with it: 340 bodies
    (EESC 186, CoR 83, Commission 45) held other articles' headlines and teasers."""
    for i in range(len(lines) // 3, len(lines)):
        if _RELATED_START.match(lines[i].strip()):
            after = [ln.strip() for ln in lines[i + 1:i + 25] if ln.strip()]
            if sum(1 for x in after if len(x) <= 40 and _ITEM_DATE.search(x)) >= 2:
                return lines[:i]
    return lines


def clean_text(text: str | None) -> str | None:
    """The same text without the lines a share widget leaves ("Share this page:",
    "Facebook", "WhatsApp", "Sign up for mail updates", "6 hours ago"), without a site
    menu stored after the article and without a list of other items under it."""
    if not text or not isinstance(text, str):
        return text
    lines = _cut_related_list(_cut_trailing_menu(text.split("\n")))
    kept = [ln for ln in lines if not _CHROME_LINE.match(ln.strip())]
    out = "\n".join(kept)
    return re.sub(r"\n{3,}", "\n\n", out).strip()
