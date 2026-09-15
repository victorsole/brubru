"""Articles from a Cellar consolidated-version XHTML, shaped for definition_extractor.

Why (15 September 2026)
-----------------------
The defined-terms endpoint parsed each act's ORIGINAL Formex text and cached the result
for ever, so a definition added by a later amendment never appeared: the AI Act served
65 terms and no "SME" or "small mid-cap", although both are in the consolidated text
(02024R1689-20260727). The consolidated XHTML is the current law, so it is what
`version=latest` reads.

The markup (Cellar CONS, checked on the AI Act): one `<div class="eli-subdivision"
id="art_N">` per article, `<p class="title-article-norm">Article 3</p>`, the heading in
`<p class="stitle-article-norm">`, numbered points as a `<span>(1) </span>` beside the
point text, and amendment markers (`<p class="modref">▼M1</p>`, `▼B`) that are not law
text and are removed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import List

from bs4 import BeautifulSoup

_MARKERS = re.compile(r"[▼►◄][A-Z]\d*")


@dataclass
class ConsolidatedArticle:
    number: str
    title: str
    text: str
    paragraphs: list = field(default_factory=list)
    html: str | None = None


def parse_consolidated_articles(xhtml: str) -> List[ConsolidatedArticle]:
    soup = BeautifulSoup(xhtml or "", "html.parser")
    out: List[ConsolidatedArticle] = []
    for div in soup.select('div.eli-subdivision[id^="art_"]'):
        # Only top-level articles: art_3, not art_3.tit_1 or a nested point.
        if not re.fullmatch(r"art_\d+[a-z]?", div.get("id") or ""):
            continue
        head = div.find("p", class_="title-article-norm")
        m = re.search(r"Article\s+(\d+[a-z]?)", head.get_text(" ", strip=True) if head else "")
        if not m:
            continue
        stitle = div.find("p", class_="stitle-article-norm")
        for junk in div.select("p.modref"):
            junk.decompose()
        if head:
            head.decompose()
        title = stitle.get_text(" ", strip=True) if stitle else ""
        if stitle:
            stitle.decompose()
        text = _MARKERS.sub(" ", div.get_text(" ", strip=True).replace("\xa0", " "))
        text = re.sub(r"\s+", " ", text).strip()
        # definition_extractor reads `.paragraphs[].text` and ignores `.text` once a
        # title is present, so the article text travels as its one paragraph.
        out.append(ConsolidatedArticle(number=m.group(1), title=title, text=text,
                                       paragraphs=[SimpleNamespace(text=text, subparagraphs=[])]))
    return out


@dataclass
class ConsolidatedLaw:
    articles: List[ConsolidatedArticle]


def parse_consolidated_law(xhtml: str) -> ConsolidatedLaw:
    return ConsolidatedLaw(articles=parse_consolidated_articles(xhtml))
