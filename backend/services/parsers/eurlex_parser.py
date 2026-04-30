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
class Subparagraph:
    """
    Subparagraph within a paragraph - can be amended separately.

    Numbered as: i., ii., iii. or (i), (ii), (iii)
    """
    number: str  # "i", "ii", "(i)", etc.
    text: str = ""


@dataclass
class Paragraph:
    """
    Paragraph within an article - can be amended separately.

    Numbered as: (1), (2), (3) or 1., 2., 3. or (a), (b), (c)
    """
    number: str  # "(1)", "1", "(a)", etc.
    text: str = ""  # Intro text (before any subparagraphs)
    subparagraphs: list[Subparagraph] = field(default_factory=list)


@dataclass
class Article:
    """Parsed article from EUR-Lex XHTML."""
    number: str
    title: str = ""
    html: str = ""
    text: str = ""  # Full plain text content of the article (for backwards compatibility)
    intro_text: str = ""  # Text before first paragraph (e.g., "For the purposes of this Regulation:")
    paragraphs: list[Paragraph] = field(default_factory=list)
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


def format_article_paragraphs(text: str) -> str:
    """
    Format article text to preserve paragraph/subparagraph structure.

    EU legislative articles have:
    - Paragraphs numbered as 1., 2., 3. etc.
    - Points/subparagraphs as (a), (b), (c) or (1), (2), (3) etc.

    This function ensures each numbered item starts on a new line for readability
    and amendability, while collapsing excessive whitespace within items.
    """
    if not text:
        return ""

    # First, normalize multiple newlines and spaces within lines
    # but preserve single newlines
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        # Collapse multiple spaces within a line
        cleaned = re.sub(r'[ \t]+', ' ', line).strip()
        if cleaned:
            cleaned_lines.append(cleaned)

    # Join with single newlines
    text = '\n'.join(cleaned_lines)

    # Ensure line breaks BEFORE numbered items that indicate new paragraphs:
    # - (1), (2), (3), ... (numbered points)
    # - (a), (b), (c), ... (lettered points)
    # - 1., 2., 3., ... (paragraph numbers)

    # Add newline before (N) where N is a number, if not already at line start
    # But avoid breaking mid-sentence references like "point (a) of paragraph 1"
    text = re.sub(r'(?<=[;.])\s*(\(\d+\))', r'\n\1', text)
    text = re.sub(r'(?<=[;.])\s*(\([a-z]\))', r'\n\1', text)

    # For items at start of content (after colon), ensure newline
    text = re.sub(r':\s*(\(\d+\))', r':\n\1', text)
    text = re.sub(r':\s*(\([a-z]\))', r':\n\1', text)

    # Ensure line breaks before standalone paragraph numbers like "1.", "2."
    # at the start of a major section
    text = re.sub(r'(?<=\n)(\d+)\.\s+', r'\1. ', text)

    # Clean up any double newlines created
    text = re.sub(r'\n\s*\n', '\n', text)

    return text.strip()


def parse_article_structure(text: str) -> tuple[str, list[Paragraph]]:
    """
    Parse article text into intro text and structured paragraphs/subparagraphs.

    EU legislative articles have hierarchical structure:
    - Intro text (before any numbered items)
    - Paragraphs: (1), (2), (3) or 1., 2., 3. or (a), (b), (c)
    - Subparagraphs within paragraphs: i., ii., iii. or (i), (ii), (iii)

    Returns:
        tuple of (intro_text, list of Paragraph objects)
    """
    if not text:
        return "", []

    # First, format the text to ensure proper line breaks
    text = format_article_paragraphs(text)
    lines = text.split('\n')

    intro_text = ""
    paragraphs = []
    current_paragraph = None

    # Patterns for paragraph numbering
    # (1), (2), etc. - numbered points in parentheses
    para_pattern_paren_num = re.compile(r'^\((\d+)\)\s*(.*)$')
    # (a), (b), etc. - lettered points in parentheses
    para_pattern_paren_letter = re.compile(r'^\(([a-z])\)\s*(.*)$')
    # 1., 2., etc. - standalone numbered paragraphs (optional space after period)
    para_pattern_dot_num = re.compile(r'^(\d+)\.\s*(.*)$')

    # Patterns for subparagraph numbering (Roman numerals i-xx)
    # Matches: i, ii, iii, iv, v, vi, vii, viii, ix, x, xi, xii, xiii, xiv, xv, xvi, xvii, xviii, xix, xx
    # i., ii., iii., etc. (optional space after period)
    subpara_pattern_roman = re.compile(r'^(x{0,2}(?:ix|iv|v?i{1,3})|x{0,2}v|x{1,2})\.\s*(.*)$', re.IGNORECASE)
    # (i), (ii), etc. - Roman in parentheses
    subpara_pattern_paren_roman = re.compile(r'^\((x{0,2}(?:ix|iv|v?i{1,3})|x{0,2}v|x{1,2})\)\s*(.*)$', re.IGNORECASE)

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for subparagraph patterns first (within current paragraph)
        subpara_match = subpara_pattern_roman.match(line) or subpara_pattern_paren_roman.match(line)
        if subpara_match and current_paragraph is not None:
            subpara_num = subpara_match.group(1)
            subpara_text = subpara_match.group(2).strip()
            current_paragraph.subparagraphs.append(Subparagraph(
                number=subpara_num,
                text=subpara_text
            ))
            continue

        # Check for paragraph patterns
        para_match = (para_pattern_paren_num.match(line) or
                      para_pattern_paren_letter.match(line) or
                      para_pattern_dot_num.match(line))

        if para_match:
            # Save previous paragraph if exists
            if current_paragraph is not None:
                paragraphs.append(current_paragraph)

            para_num = para_match.group(1)
            para_text = para_match.group(2).strip()

            # Determine the format to preserve in the number
            if para_pattern_paren_num.match(line):
                para_num = f"({para_num})"
            elif para_pattern_paren_letter.match(line):
                para_num = f"({para_num})"
            # For dot_num, keep just the number

            current_paragraph = Paragraph(
                number=para_num,
                text=para_text,
                subparagraphs=[]
            )
        elif current_paragraph is not None:
            # Continuation of current paragraph text
            if current_paragraph.text:
                current_paragraph.text += " " + line
            else:
                current_paragraph.text = line
        else:
            # Intro text (before any paragraph)
            if intro_text:
                intro_text += " " + line
            else:
                intro_text = line

    # Don't forget the last paragraph
    if current_paragraph is not None:
        paragraphs.append(current_paragraph)

    return intro_text.strip(), paragraphs


class EurlexParser:
    """
    Parser for EUR-Lex XHTML documents.

    Handles three main formats:
    1. Official Journal (OJ) style - adopted legislation from EUR-Lex
    2. Consolidated style - merged versions
    3. COM document style - Commission proposals (CELEX starting with 5)
    """

    def __init__(self):
        self.soup: Optional[BeautifulSoup] = None
        self.is_com_document: bool = False

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

        # Detect document type (COM proposal vs OJ adopted)
        self.is_com_document = self._detect_com_document()

        # Extract metadata
        result.title, result.short_title = self._extract_title()
        result.celex = self._extract_celex()

        # Extract content based on document type
        if self.is_com_document:
            result.recitals = self._extract_recitals_com()
            result.articles = self._extract_articles_com()
        else:
            result.recitals = self._extract_recitals()
            result.articles = self._extract_articles()

        result.annexes = self._extract_annexes()

        return result

    def _detect_com_document(self) -> bool:
        """Detect if this is a COM document (proposal) vs OJ (adopted legislation).

        Cellar API XHTML for OJ-published regulations uses `eli-subdivision`
        DIVs with `id^="rct_"` for recitals and `oj-*` classes — those are
        unambiguous OJ markers. If we see them, this is OJ-adopted, even if
        the body cites a COM proposal in the recitals (which most regulations
        do — they reference the original COM proposal in the preamble).
        """
        if not self.soup:
            return False

        # OJ-adopted markers — strong signal, takes precedence
        oj_markers = [
            self.soup.select_one('div.eli-subdivision[id^="rct_"]'),  # recitals
            self.soup.select_one('div.oj-final'),
            self.soup.select_one('p.oj-doc-ti'),
            self.soup.select_one('p.oj-ti-art'),
        ]
        if any(oj_markers):
            return False

        # COM documents have specific CSS classes
        com_indicators = [
            self.soup.select_one('.ManualConsidrant'),  # Recitals in COM format
            self.soup.select_one('.ManualHeading1'),     # Section headings
            self.soup.select_one('.Typedudocument'),     # Document type header
            self.soup.select_one('.Rfrenceinstitutionnelle'),  # COM reference
            self.soup.select_one('.Exposdesmotifstitre'),  # Explanatory memorandum
        ]
        if any(com_indicators):
            return True

        # Final fallback: COM reference pattern in absence of OJ markers
        text = self.soup.get_text()
        return bool(re.search(r'COM\s*\(\d{4}\)\s*\d+', text))

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

    def _format_article_paragraphs(self, text: str) -> str:
        """Format article text - delegates to standalone function."""
        return format_article_paragraphs(text)

    def _extract_title(self) -> tuple[str, str]:
        """Extract main title and short title from document."""
        if not self.soup:
            return "", ""

        main_title = ""
        short_title = ""

        # Find main title element - check both OJ and COM format selectors
        title_el = self.soup.select_one(
            '.oj-doc-ti, .doc-ti, .title-doc-first, '
            '.Titreobjet, .Titreobjet_cp'  # COM document title classes
        )
        if title_el:
            main_title = self._format_title(self._get_text(title_el))

        # For COM documents, also check for document type prefix
        if self.is_com_document:
            type_el = self.soup.select_one('.Typedudocument, .Typedudocument_cp')
            if type_el and main_title:
                doc_type = self._get_text(type_el)
                if doc_type and doc_type not in main_title:
                    main_title = f"{doc_type} — {main_title}"

        # Look for short title in parentheses
        doc_titles = self.soup.select('.oj-doc-ti, .doc-ti, .Titreobjet, .Titreobjet_cp')
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

                # Extract article text content from container
                article_text = ""
                if container:
                    # Get all text, excluding title elements
                    for p in container.find_all(['p', 'table']):
                        p_classes = p.get('class', [])
                        # Skip title/header elements
                        if not any(c in p_classes for c in ['oj-ti-art', 'oj-sti-art', 'eli-title']):
                            article_text += self._get_text(p) + "\n"
                article_text = article_text.strip()

                # Format and parse article text into structured paragraphs
                article_text = self._format_article_paragraphs(article_text)
                intro_text, paragraphs = parse_article_structure(article_text)

                articles.append(Article(
                    number=article_number,
                    title=article_title,
                    html=self._get_inner_html(container or el.parent),
                    text=article_text,
                    intro_text=intro_text,
                    paragraphs=paragraphs,
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

                    # Extract article text content
                    article_text = ""
                    for p in el.find_all(['p', 'table']):
                        p_classes = p.get('class', [])
                        # Skip title/header elements
                        if not any(c in p_classes for c in ['title-article-norm', 'stitle-article-norm']):
                            article_text += self._get_text(p) + "\n"
                    article_text = article_text.strip()

                    division = Division(
                        chapter_number=current_chapter.chapter_number,
                        chapter_title=current_chapter.chapter_title,
                        section_number=current_section.section_number,
                        section_title=current_section.section_title
                    )

                    # Format and parse article text into structured paragraphs
                    article_text = self._format_article_paragraphs(article_text)
                    intro_text, paragraphs = parse_article_structure(article_text)

                    articles.append(Article(
                        number=article_number,
                        title=article_title,
                        html=self._get_inner_html(el),
                        text=article_text,
                        intro_text=intro_text,
                        paragraphs=paragraphs,
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

    # ===== COM Document (Proposal) Extraction Methods =====

    def _find_proposal_section(self):
        """
        Find the start of the actual Proposal section in COM documents.

        COM documents have:
        1. Explanatory Memorandum (ends around first procedure code)
        2. Proposal itself (starts with second procedure code like "2025/0543 (COD)")

        Returns the BeautifulSoup element or position marker for the Proposal start.
        """
        if not self.soup:
            return None

        # Get full text to find procedure code positions
        full_text = self.soup.get_text()

        # Find procedure code pattern (e.g., "2025/0543 (COD)")
        procedure_pattern = re.compile(r'\d{4}/\d{4}\s*\([A-Z]{3}\)')
        matches = list(procedure_pattern.finditer(full_text))

        if len(matches) >= 2:
            # The Proposal starts after the SECOND occurrence
            second_match_pos = matches[1].start()

            # Now find the element that contains or is near this position
            # Look for "Whereas:" after this position
            proposal_text = full_text[second_match_pos:]

            return second_match_pos, proposal_text

        return 0, full_text

    def _extract_recitals_com(self) -> list[Recital]:
        """Extract recitals from COM document (proposal format)."""
        if not self.soup:
            return []

        recitals = []

        # First, try CSS selectors for HTML-structured documents
        manual_recitals = self.soup.select('p.ManualConsidrant, p.li.ManualConsidrant')

        if manual_recitals:
            # Use CSS-based extraction
            for el in manual_recitals:
                num_el = el.select_one('span.num')
                if num_el:
                    num_text = self._get_text(num_el)
                    num_match = re.search(r'\((\d+)\)', num_text)
                    recital_number = num_match.group(1) if num_match else num_text.strip('() ')
                else:
                    recital_number = str(len(recitals) + 1)

                text = self._get_text(el)
                text = re.sub(r'^\s*\(\d+\)\s*', '', text)

                if text:
                    recitals.append(Recital(
                        number=recital_number,
                        text=text,
                        html=self._get_inner_html(el)
                    ))
        else:
            # Fallback: text-based extraction from Proposal section
            _, proposal_text = self._find_proposal_section()

            # Find "Whereas:" marker
            whereas_match = re.search(r'\bWhereas\s*:', proposal_text, re.IGNORECASE)
            if whereas_match:
                # Find where articles start (same broadened enacting formula as _extract_articles_com)
                articles_start = re.search(
                    r'(?:HAVE|HAS)\s+ADOPTED\s+(?:THIS\s+)?(?:REGULATION|DIRECTIVE|DECISION|THE\s+FOLLOWING\s+(?:REGULATION|DIRECTIVE|DECISION))'
                    r'|(?:HAVE|HAS)\s+DECIDED\s+AS\s+FOLLOWS'
                    r'|HEREBY\s+DECIDE[SD]?'
                    r'|\bArticle\s+1\b',
                    proposal_text,
                    re.IGNORECASE
                )
                end_pos = articles_start.start() if articles_start else len(proposal_text)

                recitals_text = proposal_text[whereas_match.end():end_pos]

                # Split by recital numbers (1), (2), etc.
                recital_pattern = re.compile(r'\((\d+)\)\s*')
                parts = recital_pattern.split(recitals_text)

                i = 1
                while i < len(parts) - 1:
                    recital_num = parts[i]
                    recital_text = parts[i + 1].strip() if i + 1 < len(parts) else ""
                    recital_text = re.sub(r'\s+', ' ', recital_text).strip()

                    if recital_text:
                        recitals.append(Recital(
                            number=recital_num,
                            text=recital_text,
                            html=""
                        ))
                    i += 2

        return recitals

    def _extract_articles_com(self) -> list[Article]:
        """
        Extract articles from COM document (proposal format).

        COM documents have:
        1. Explanatory Memorandum (with headings like "CONTEXT OF THE PROPOSAL")
        2. The Proposal itself (after second procedure code like "2025/0543 (COD)")
           - Recitals starting with "Whereas:"
           - "HAS ADOPTED THIS REGULATION/DIRECTIVE:"
           - Article 1, Article 2, etc.

        We ONLY extract from the Proposal section, skipping the Explanatory Memorandum.
        """
        if not self.soup:
            return []

        articles = []

        # Get the proposal section (skip Explanatory Memorandum)
        proposal_start_pos, proposal_text = self._find_proposal_section()

        # First try: text-based extraction from proposal section
        # Find "HAS ADOPTED" or similar enacting formula in proposal text
        # Covers: HAS ADOPTED THIS REGULATION/DIRECTIVE/DECISION,
        # HAVE ADOPTED THIS..., HAS DECIDED AS FOLLOWS, HEREBY DECIDES,
        # HAS ADOPTED THE FOLLOWING REGULATION, etc.
        adopted_match = re.search(
            r'(?:HAVE|HAS)\s+ADOPTED\s+(?:THIS\s+)?(?:REGULATION|DIRECTIVE|DECISION|THE\s+FOLLOWING\s+(?:REGULATION|DIRECTIVE|DECISION))'
            r'|(?:HAVE|HAS)\s+DECIDED\s+AS\s+FOLLOWS'
            r'|HEREBY\s+DECIDE[SD]?',
            proposal_text,
            re.IGNORECASE
        )

        # Fallback: if no enacting formula found, try to find "Article 1" directly
        if not adopted_match:
            adopted_match = re.search(r'(?:^|\n)\s*Article\s+1\b', proposal_text, re.IGNORECASE)

        articles_start_in_proposal = adopted_match.end() if adopted_match else 0
        articles_text = proposal_text[articles_start_in_proposal:]

        # Find Article headings - must be at START OF LINE to avoid matching
        # references like "as defined in Article 2 of the Annex"
        # Pattern: newline (or start) + optional whitespace + "Article" + number
        article_pattern = re.compile(r'(?:^|\n)\s*Article\s+(\d+[a-z]?)\b', re.IGNORECASE)
        article_matches = list(article_pattern.finditer(articles_text))

        if article_matches:
            # Extract articles from text
            for i, match in enumerate(article_matches):
                article_num = match.group(1)

                # Get text until next article heading or end
                start_pos = match.end()
                if i + 1 < len(article_matches):
                    end_pos = article_matches[i + 1].start()
                else:
                    # Stop at ANNEX or end
                    annex_match = re.search(r'(?:^|\n)\s*ANNEX\b', articles_text[start_pos:], re.IGNORECASE)
                    end_pos = start_pos + annex_match.start() if annex_match else len(articles_text)

                article_content = articles_text[start_pos:end_pos].strip()

                # Extract title (first line if it's short and looks like a title)
                lines = article_content.split('\n')
                article_title = ""
                article_text = article_content

                if lines:
                    first_line = lines[0].strip()
                    # If first line is short and looks like a title (not numbered paragraph)
                    if (len(first_line) < 100 and
                        not first_line.startswith('1.') and
                        not first_line.startswith('(') and
                        not re.match(r'^\d+\.', first_line)):
                        article_title = first_line
                        article_text = '\n'.join(lines[1:]).strip()

                # Format text: preserve paragraph structure
                # Keep line breaks before numbered items: (1), (2), 1., 2., (a), (b), etc.
                article_text = self._format_article_paragraphs(article_text)

                # Parse into structured paragraphs and subparagraphs
                intro_text, paragraphs = parse_article_structure(article_text)

                articles.append(Article(
                    number=article_num,
                    title=article_title,
                    text=article_text,  # Keep full text for backwards compatibility
                    intro_text=intro_text,
                    paragraphs=paragraphs,
                    html="",
                    division=None
                ))

            return articles

        # Fallback: Try HTML-based extraction but only for elements in the proposal section
        # Get full document text to determine positions
        full_text = self.soup.get_text()

        article_elements = []
        for el in self.soup.find_all('p'):
            text = self._get_text(el)
            article_match = re.match(r'^Article\s+(\d+[a-z]?)\s*$', text, re.IGNORECASE)
            if article_match:
                # Check if this element appears AFTER the proposal start
                # by finding its position in the full text
                el_text_sample = text[:50]  # Use text sample to locate
                el_position = full_text.find(el_text_sample)

                # Only include if it's in the proposal section
                if el_position >= proposal_start_pos:
                    article_number = article_match.group(1)

                    # Look for title in next element
                    next_el = el.find_next_sibling('p')
                    article_title = ""
                    if next_el:
                        next_text = self._get_text(next_el)
                        # Skip if next is another Article
                        if not re.match(r'^Article\s+\d+', next_text, re.IGNORECASE):
                            article_title = next_text

                    article_elements.append((el, article_number, article_title))

        if article_elements:
            for el, number, title in article_elements:
                # Extract article content - get all following paragraphs until next Article
                article_text = ""
                next_sibling = el.find_next_sibling()
                while next_sibling:
                    sibling_text = self._get_text(next_sibling)
                    # Stop if we hit another Article heading or ANNEX
                    if (re.match(r'^Article\s+\d+', sibling_text, re.IGNORECASE) or
                        re.match(r'^ANNEX', sibling_text, re.IGNORECASE)):
                        break
                    article_text += sibling_text + "\n"
                    next_sibling = next_sibling.find_next_sibling()
                article_text = article_text.strip()

                # Format and parse into structured paragraphs
                article_text = self._format_article_paragraphs(article_text)
                intro_text, paragraphs = parse_article_structure(article_text)

                articles.append(Article(
                    number=number,
                    title=title,
                    html=self._get_inner_html(el.parent) if el.parent else "",
                    text=article_text,
                    intro_text=intro_text,
                    paragraphs=paragraphs,
                    division=None
                ))

        return articles


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


def parse_com_document_text(text: str, celex: str = "") -> ParsedEurlexDocument:
    """
    Parse COM document (proposal) from plain text.

    Used when HTML parsing fails (e.g., WAF blocked) and we have PDF-extracted text.

    COM documents have this structure:
    1. Explanatory Memorandum (Context, Legal basis, Evaluations, Budget, Other)
    2. The Proposal itself (starts after procedure code reappears)
       - "Having regard to..." citations
       - "Whereas:" followed by numbered recitals (1), (2), etc.
       - "HAS ADOPTED THIS REGULATION/DIRECTIVE:"
       - Articles (Article 1, Article 2, etc.)

    Args:
        text: Plain text content from PDF
        celex: Optional CELEX number for metadata

    Returns:
        ParsedEurlexDocument with recitals and articles
    """
    result = ParsedEurlexDocument(celex=celex)

    # Find the procedure code pattern (e.g., "2025/0543 (COD)")
    procedure_pattern = re.compile(r'\d{4}/\d{4}\s*\([A-Z]{3}\)')
    procedure_matches = list(procedure_pattern.finditer(text))

    # The Proposal starts after the SECOND occurrence of the procedure code
    proposal_start = 0
    if len(procedure_matches) >= 2:
        proposal_start = procedure_matches[1].end()
    elif len(procedure_matches) == 1:
        # Only one occurrence, use it
        proposal_start = procedure_matches[0].end()

    proposal_text = text[proposal_start:]

    # Extract title - look for "REGULATION/DIRECTIVE OF THE EUROPEAN PARLIAMENT"
    title_match = re.search(
        r'(?:Proposal for a\s+)?(REGULATION|DIRECTIVE|DECISION)\s+OF\s+THE\s+EUROPEAN\s+PARLIAMENT\s+AND\s+(?:OF\s+)?THE\s+COUNCIL[^(]+',
        proposal_text,
        re.IGNORECASE | re.DOTALL
    )
    if title_match:
        result.title = re.sub(r'\s+', ' ', title_match.group()).strip()

    # Find where recitals start ("Whereas:")
    whereas_match = re.search(r'\bWhereas\s*:', proposal_text, re.IGNORECASE)

    # Find where articles start ("HAS ADOPTED" or "Article 1")
    adopted_match = re.search(
        r'(?:HAVE|HAS)\s+ADOPTED\s+THIS\s+(?:REGULATION|DIRECTIVE|DECISION)',
        proposal_text,
        re.IGNORECASE
    )
    article_1_match = re.search(r'\bArticle\s+1\b', proposal_text, re.IGNORECASE)

    # Determine boundaries
    recitals_start = whereas_match.end() if whereas_match else 0

    if adopted_match:
        recitals_end = adopted_match.start()
        articles_start = adopted_match.end()
    elif article_1_match:
        recitals_end = article_1_match.start()
        articles_start = article_1_match.start()
    else:
        recitals_end = len(proposal_text)
        articles_start = len(proposal_text)

    # Extract recitals - pattern: (1), (2), etc.
    if whereas_match and recitals_start < recitals_end:
        recitals_text = proposal_text[recitals_start:recitals_end]

        # Split by recital numbers (1), (2), etc.
        recital_pattern = re.compile(r'\((\d+)\)\s*')
        parts = recital_pattern.split(recitals_text)

        # parts will be: [text_before, num1, text1, num2, text2, ...]
        i = 1
        while i < len(parts) - 1:
            recital_num = parts[i]
            recital_text = parts[i + 1].strip() if i + 1 < len(parts) else ""

            # Clean up the recital text
            recital_text = re.sub(r'\s+', ' ', recital_text).strip()

            if recital_text:
                result.recitals.append(Recital(
                    number=recital_num,
                    text=recital_text,
                    html=""
                ))
            i += 2

    # Extract articles - pattern: Article N at START OF LINE (not mid-sentence references)
    if articles_start < len(proposal_text):
        articles_text = proposal_text[articles_start:]

        # Match Article headings only at line start to avoid false positives
        # from references like "as defined in Article 2 of the Annex"
        article_pattern = re.compile(r'(?:^|\n)\s*Article\s+(\d+[a-z]?)\b', re.IGNORECASE)
        article_matches = list(article_pattern.finditer(articles_text))

        for i, match in enumerate(article_matches):
            article_num = match.group(1)

            # Get text until next article heading or end
            start_pos = match.end()
            if i + 1 < len(article_matches):
                end_pos = article_matches[i + 1].start()
            else:
                # Stop at ANNEX or end
                annex_match = re.search(r'(?:^|\n)\s*ANNEX\b', articles_text[start_pos:], re.IGNORECASE)
                end_pos = start_pos + annex_match.start() if annex_match else len(articles_text)

            article_content = articles_text[start_pos:end_pos].strip()

            # Extract title (first line or sentence)
            lines = article_content.split('\n')
            article_title = ""
            article_text = article_content

            if lines:
                first_line = lines[0].strip()
                # If first line is short and looks like a title
                if (len(first_line) < 100 and
                    not first_line.startswith('1.') and
                    not first_line.startswith('(') and
                    not re.match(r'^\d+\.', first_line)):
                    article_title = first_line
                    article_text = '\n'.join(lines[1:]).strip()

            # Format text: preserve paragraph structure
            article_text = format_article_paragraphs(article_text)

            # Parse into structured paragraphs and subparagraphs
            intro_text, paragraphs = parse_article_structure(article_text)

            result.articles.append(Article(
                number=article_num,
                title=article_title,
                text=article_text,
                intro_text=intro_text,
                paragraphs=paragraphs,
                html="",
                division=None
            ))

    return result
