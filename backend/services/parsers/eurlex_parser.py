"""
EUR-Lex XHTML Parser

Parses EUR-Lex web pages (XHTML format) to extract structured legal content.
Handles both Official Journal (OJ) and consolidated versions.

Based on LegalViz parsers.js implementation.

Usage:
    from services.parsers.eurlex_parser import EurlexParser, parse_eurlex_html

    parser = EurlexParser()
    result = parser.parse_html(html_content)
    # or
    result = parse_eurlex_html(html_content)
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from bs4 import BeautifulSoup, NavigableString


@dataclass
class Division:
    """Chapter/Section division info."""
    chapter_number: str = ""
    chapter_title: str = ""
    section_number: str = ""
    section_title: str = ""


@dataclass
class Article:
    """Parsed article from EUR-Lex XHTML."""
    number: str
    title: str = ""
    html: str = ""
    division: Optional[Division] = None


@dataclass
class Recital:
    """Parsed recital from EUR-Lex XHTML."""
    number: str
    text: str = ""
    html: str = ""


@dataclass
class Annex:
    """Parsed annex from EUR-Lex XHTML."""
    id: str
    title: str = ""
    html: str = ""


@dataclass
class ParsedEurlexDocument:
    """Complete parsed EUR-Lex XHTML document."""
    title: str = ""
    short_title: str = ""
    celex: str = ""
    articles: list[Article] = field(default_factory=list)
    recitals: list[Recital] = field(default_factory=list)
    annexes: list[Annex] = field(default_factory=list)


class EurlexParser:
    """
    Parser for EUR-Lex XHTML documents.

    Handles two main formats:
    1. Official Journal (OJ) style - direct from EUR-Lex
    2. Consolidated style - merged versions
    """

    def __init__(self):
        self.soup: Optional[BeautifulSoup] = None

    def parse_html(self, html_content: str) -> ParsedEurlexDocument:
        """
        Parse EUR-Lex XHTML content into structured data.

        Args:
            html_content: Raw HTML/XHTML string from EUR-Lex

        Returns:
            ParsedEurlexDocument with extracted title, articles, recitals, annexes
        """
        self.soup = BeautifulSoup(html_content, 'html.parser')

        result = ParsedEurlexDocument()

        # Extract metadata
        result.title, result.short_title = self._extract_title()
        result.celex = self._extract_celex()

        # Extract content
        result.recitals = self._extract_recitals()
        result.articles = self._extract_articles()
        result.annexes = self._extract_annexes()

        return result

    def _get_text(self, element) -> str:
        """Get clean text content from element."""
        if element is None:
            return ""
        text = element.get_text()
        return re.sub(r'\s+', ' ', text).strip()

    def _get_inner_html(self, element) -> str:
        """Get inner HTML of element."""
        if element is None:
            return ""
        return ''.join(str(child) for child in element.children)

    def _normalize(self, s: str) -> str:
        """Normalize whitespace in string."""
        return re.sub(r'\s+', ' ', s.replace('\u00a0', ' ')).strip()

    def _format_title(self, t: str) -> str:
        """Format title - cut after 'of' and title case."""
        if not t:
            return ""
        # Cut after " of " (case insensitive)
        parts = re.split(r'\s+of\s+', t, flags=re.IGNORECASE)
        short = parts[0]
        # Title case
        result = short.lower()
        result = re.sub(r'(?:^|\s)\S', lambda m: m.group().upper(), result)
        # Fix acronyms
        result = re.sub(r'\b(Eu|Ec|Eec|Euratom)\b',
                       lambda m: m.group().upper(), result, flags=re.IGNORECASE)
        return result

    def _extract_title(self) -> tuple[str, str]:
        """Extract main title and short title from document."""
        if not self.soup:
            return "", ""

        main_title = ""
        short_title = ""

        # Find main title element
        title_el = self.soup.select_one('.oj-doc-ti, .doc-ti, .title-doc-first')
        if title_el:
            main_title = self._format_title(self._get_text(title_el))

        # Look for short title in parentheses
        doc_titles = self.soup.select('.oj-doc-ti, .doc-ti')
        for el in doc_titles:
            txt = self._get_text(el)
            # Match pattern like "... (Artificial Intelligence Act)" at end
            match = re.search(r'\(([^)]+)\)$', txt)
            if match:
                candidate = match.group(1).strip()
                # Filter out EEA relevance and date patterns
                if ('text with eea relevance' not in candidate.lower() and
                    not re.match(r'^\d{4}/\d+$', candidate) and
                    3 < len(candidate) < 100):
                    short_title = candidate
                    break

        # Combine titles
        if short_title and main_title and short_title not in main_title:
            final_title = f"{short_title} — {main_title}"
        else:
            final_title = short_title or main_title

        return final_title, short_title

    def _extract_celex(self) -> str:
        """Extract CELEX number from document metadata."""
        if not self.soup:
            return ""

        # Try meta tag
        meta = self.soup.find('meta', {'name': 'celex'})
        if meta and meta.get('content'):
            return meta['content']

        # Try to find in URL or document
        # CELEX pattern: e.g., 32024R1689, 32016R0679
        celex_pattern = re.compile(r'\b[0-9]{5}[A-Z][0-9]{4}\b')

        # Check link elements
        for link in self.soup.find_all('a', href=True):
            href = link['href']
            if 'eur-lex.europa.eu' in href:
                match = celex_pattern.search(href)
                if match:
                    return match.group()

        # Check text content
        text = self.soup.get_text()
        match = celex_pattern.search(text)
        if match:
            return match.group()

        return ""

    def _extract_recitals(self) -> list[Recital]:
        """Extract recitals from document."""
        if not self.soup:
            return []

        recitals = []

        # OJ style: DIV.eli-subdivision with id starting with rct_
        for div in self.soup.select('div.eli-subdivision[id^="rct_"]'):
            tds = div.select('table td')
            if len(tds) >= 2:
                # First td contains number, second contains text
                num_match = re.search(r'\(?\s*(\d+)\s*\)?', tds[0].get_text())
                recital_number = num_match.group(1) if num_match else self._get_text(tds[0])
                text_cell = tds[1]
                recitals.append(Recital(
                    number=recital_number,
                    text=self._get_text(text_cell),
                    html=self._get_inner_html(text_cell)
                ))
            else:
                # Fallback: take the whole block
                num_el = div.select_one('.recital-number, .oj-recital-num, strong')
                if num_el:
                    recital_number = re.sub(r'\D+', '', self._get_text(num_el)) or str(len(recitals) + 1)
                else:
                    recital_number = str(len(recitals) + 1)
                recitals.append(Recital(
                    number=recital_number,
                    text=self._get_text(div),
                    html=self._get_inner_html(div)
                ))

        # Sort by number
        recitals.sort(key=lambda r: int(r.number) if r.number.isdigit() else 0)

        return recitals

    def _extract_articles(self) -> list[Article]:
        """Extract articles from document."""
        if not self.soup:
            return []

        articles = []
        current_chapter = Division()
        current_section = Division()
        pending_header = None  # "chapter" or "section"

        # Walk through all elements
        for el in self.soup.descendants:
            if not hasattr(el, 'name') or el.name is None:
                continue

            # Division headings
            if el.name == 'p' and el.get('class'):
                classes = el.get('class', [])
                if 'title-division-1' in classes or 'oj-ti-section-1' in classes:
                    txt = self._normalize(self._get_text(el))
                    upper = txt.upper()

                    if re.match(r'^\s*CHAPTER\b', upper):
                        current_chapter = Division(chapter_number=txt)
                        current_section = Division()
                        pending_header = "chapter"
                    elif re.match(r'^\s*SECTION\b', upper):
                        current_section = Division(section_number=txt)
                        pending_header = "section"
                    else:
                        current_chapter = Division(chapter_number=txt)
                        current_section = Division()
                        pending_header = "chapter"

                if 'title-division-2' in classes or 'oj-ti-section-2' in classes:
                    txt = self._normalize(self._get_text(el))
                    if pending_header == "chapter":
                        current_chapter.chapter_title = txt
                    elif pending_header == "section":
                        current_section.section_title = txt
                    pending_header = None

            # Articles - OJ style
            if el.name == 'p' and el.get('class') and 'oj-ti-art' in el.get('class', []):
                # Find container
                container = el.parent
                while container and not (container.name == 'div' and
                                        'eli-subdivision' in container.get('class', [])):
                    container = container.parent

                # Extract article number
                num_match = re.search(r'Article\s+(\d+)', self._get_text(el), re.IGNORECASE)
                article_number = num_match.group(1) if num_match else self._get_text(el)

                # Extract article title
                title_block = container.select_one('div.eli-title p.oj-sti-art') if container else None
                article_title = self._get_text(title_block) if title_block else ""

                division = Division(
                    chapter_number=current_chapter.chapter_number,
                    chapter_title=current_chapter.chapter_title,
                    section_number=current_section.section_number,
                    section_title=current_section.section_title
                )

                articles.append(Article(
                    number=article_number,
                    title=article_title,
                    html=self._get_inner_html(container or el.parent),
                    division=division
                ))
                continue

            # Articles - consolidated style
            if el.name == 'div' and 'eli-subdivision' in el.get('class', []):
                num_p = el.select_one('p.title-article-norm')
                if num_p:
                    num_match = re.search(r'Article\s+(\d+)', num_p.get_text(), re.IGNORECASE)
                    article_number = num_match.group(1) if num_match else num_p.get_text().strip()

                    title_p = el.select_one('p.stitle-article-norm')
                    article_title = self._get_text(title_p) if title_p else ""

                    division = Division(
                        chapter_number=current_chapter.chapter_number,
                        chapter_title=current_chapter.chapter_title,
                        section_number=current_section.section_number,
                        section_title=current_section.section_title
                    )

                    articles.append(Article(
                        number=article_number,
                        title=article_title,
                        html=self._get_inner_html(el),
                        division=division
                    ))

        return articles

    def _extract_annexes(self) -> list[Annex]:
        """Extract annexes from document."""
        if not self.soup:
            return []

        annexes = []

        for el in self.soup.find_all('p'):
            classes = el.get('class', [])
            txt = self._get_text(el)

            # Check if this looks like an annex heading
            looks_like_annex = (
                re.match(r'^ANNEX(\s+[IVXLC]+|\s+\d+)?', txt, re.IGNORECASE) or
                'oj-ti-annex' in classes or
                'oj-ti-annex-1' in classes or
                'title-annex-norm' in classes
            )

            if looks_like_annex:
                title = txt

                # Look for subtitle
                title_p = None
                parent = el.parent
                if parent:
                    title_p = parent.select_one(
                        'div.eli-title p, p.oj-ti-annex-2, p.stitle-annex-norm'
                    )

                # Check next sibling for subtitle
                if not title_p:
                    next_el = el.find_next_sibling('p')
                    if next_el and next_el.get('class'):
                        next_classes = next_el.get('class', [])
                        if 'oj-doc-ti' in next_classes or 'oj-normal' in next_classes:
                            title_p = next_el

                if title_p:
                    title = f"{txt} — {self._get_text(title_p)}"

                # Find container
                container = el.parent
                while container and not (container.name == 'div' and
                                        'eli-subdivision' in container.get('class', [])):
                    container = container.parent

                root = container or el.parent or el
                annex_html = self._get_inner_html(root)

                # Extract annex ID/number
                match = re.match(r'^ANNEX\s*([IVXLC]+|\d+)?', txt, re.IGNORECASE)
                annex_id = match.group(1).strip() if match and match.group(1) else title

                annexes.append(Annex(
                    id=annex_id,
                    title=title,
                    html=annex_html
                ))

        return annexes


def parse_eurlex_html(html_content: str) -> ParsedEurlexDocument:
    """
    Convenience function to parse EUR-Lex XHTML.

    Args:
        html_content: Raw HTML/XHTML string from EUR-Lex

    Returns:
        ParsedEurlexDocument with extracted content
    """
    parser = EurlexParser()
    return parser.parse_html(html_content)
