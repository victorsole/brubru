"""
Formex XML Parser

Parses EU legal documents in Formex XML format (from EUR-Lex/LEG_2025-11 archive).

Formex is the official XML format used by the Publications Office of the EU.
This parser extracts structured data from these documents including:
- Bibliographic metadata (CELEX, OJ reference, date)
- Title and document type
- Recitals (considerations/whereas clauses)
- Articles with paragraphs
- Annexes
- Legal basis and citations
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class Paragraph:
    """A paragraph within an article."""
    number: str
    identifier: str
    text: str
    html: str


@dataclass
class Article:
    """An article in a legal document."""
    number: str
    identifier: str
    title: str
    paragraphs: list[Paragraph] = field(default_factory=list)
    html: str = ""
    chapter: str = ""
    chapter_title: str = ""
    section: str = ""
    section_title: str = ""


@dataclass
class Recital:
    """A recital (consideration/whereas clause)."""
    number: str
    text: str
    html: str = ""


@dataclass
class Annex:
    """An annex to the legal document."""
    id: str
    title: str
    html: str = ""


@dataclass
class ParsedLaw:
    """Complete parsed legal document."""
    # Identifiers
    celex: Optional[str] = None
    oj_reference: Optional[str] = None

    # Metadata
    title: str = ""
    short_title: str = ""
    doc_type: str = ""
    date: Optional[date] = None
    language: str = "EN"

    # Structure
    articles: list[Article] = field(default_factory=list)
    recitals: list[Recital] = field(default_factory=list)
    annexes: list[Annex] = field(default_factory=list)

    # Legal relationships
    legal_basis: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)

    # Extra metadata
    page_count: int = 0
    eea_relevance: bool = False

    # Source
    source_file: str = ""


class FormexParser:
    """
    Parser for Formex XML documents.

    Usage:
        parser = FormexParser()
        result = parser.parse_file('/path/to/document.xml')

        # Or parse string content
        result = parser.parse_string(xml_content)
    """

    def __init__(self):
        self.namespaces = {}  # Formex usually doesn't use namespaces

    def parse_file(self, file_path: str | Path) -> ParsedLaw:
        """Parse a Formex XML file."""
        file_path = Path(file_path)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            result = self.parse_string(content)
            result.source_file = str(file_path)
            return result

        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            raise

    def parse_string(self, xml_content: str) -> ParsedLaw:
        """Parse Formex XML content string."""
        result = ParsedLaw()

        try:
            # Clean up XML for parsing (handle potential issues)
            xml_content = self._clean_xml(xml_content)
            root = ET.fromstring(xml_content)

            # Extract all components
            self._extract_bibliographic(root, result)
            self._extract_title(root, result)
            self._extract_recitals(root, result)
            self._extract_articles(root, result)
            self._extract_annexes(root, result)
            self._extract_legal_basis(root, result)

        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")
            # Try fallback regex-based extraction for malformed XML
            self._fallback_extraction(xml_content, result)

        return result

    def _clean_xml(self, content: str) -> str:
        """Clean XML content for parsing."""
        # Remove BOM if present
        if content.startswith('\ufeff'):
            content = content[1:]

        # Fix common XML issues
        content = content.replace('&nbsp;', '&#160;')
        content = content.replace('&', '&amp;').replace('&amp;amp;', '&amp;')
        content = content.replace('&amp;#', '&#')
        content = content.replace('&amp;lt;', '&lt;')
        content = content.replace('&amp;gt;', '&gt;')

        return content

    def _get_text(self, element: Optional[ET.Element], default: str = "") -> str:
        """Extract all text content from an element."""
        if element is None:
            return default

        text_parts = []
        for item in element.iter():
            if item.text:
                text_parts.append(item.text)
            if item.tail:
                text_parts.append(item.tail)

        return ' '.join(text_parts).strip()

    def _get_inner_html(self, element: Optional[ET.Element]) -> str:
        """Get the inner content of an element as HTML-like string."""
        if element is None:
            return ""

        return ET.tostring(element, encoding='unicode', method='html')

    def _extract_bibliographic(self, root: ET.Element, result: ParsedLaw):
        """Extract bibliographic metadata."""
        bib = root.find('.//BIB.INSTANCE')
        if bib is None:
            return

        # Document reference
        doc_ref = bib.find('.//DOCUMENT.REF')
        if doc_ref is not None:
            coll = doc_ref.findtext('COLL', '')
            year_el = doc_ref.find('.//NO.DOC/YEAR')
            no_el = doc_ref.find('.//NO.DOC/NO.CURRENT')

            year = year_el.text if year_el is not None else ''
            no = no_el.text if no_el is not None else ''

            # Construct OJ reference
            page_first = doc_ref.findtext('PAGE.FIRST', '')
            if coll and year and no:
                result.oj_reference = f"{coll} {year}/{no}"
                if page_first:
                    result.oj_reference += f", p. {page_first}"

        # Date
        date_el = bib.find('.//DATE[@ISO]')
        if date_el is not None:
            iso_date = date_el.get('ISO', '')
            if iso_date and len(iso_date) == 8:
                try:
                    result.date = date(
                        int(iso_date[:4]),
                        int(iso_date[4:6]),
                        int(iso_date[6:8])
                    )
                except ValueError:
                    pass

        # Language
        result.language = bib.findtext('.//LG.DOC', 'EN')

        # Page count
        page_total = bib.findtext('.//PAGE.TOTAL')
        if page_total:
            try:
                result.page_count = int(page_total)
            except ValueError:
                pass

        # EEA relevance
        eea = bib.find('.//EEA')
        result.eea_relevance = eea is not None

        # Try to construct CELEX from document info
        no_doc = bib.find('.//NO.DOC')
        if no_doc is not None:
            year = no_doc.findtext('YEAR', '')
            no_current = no_doc.findtext('NO.CURRENT', '')
            com = no_doc.findtext('COM', '')

            if year and no_current:
                # Guess document type from title
                doc_type_code = 'R'  # Default to Regulation
                result.celex = f"3{year}{doc_type_code}{no_current.zfill(4)}"

    def _extract_title(self, root: ET.Element, result: ParsedLaw):
        """Extract document title and type."""
        title_el = root.find('.//TITLE/TI')
        if title_el is None:
            return

        # Get all paragraphs in title
        paragraphs = title_el.findall('.//P')
        title_parts = []

        for p in paragraphs:
            text = self._get_text(p)
            if text:
                title_parts.append(text)

        full_title = ' '.join(title_parts)
        result.title = full_title

        # Extract document type from first paragraph (usually in HT TYPE="UC")
        ht = title_el.find('.//HT[@TYPE="UC"]')
        if ht is not None and ht.text:
            result.doc_type = ht.text.strip()

        # Extract short title from parentheses at end
        # e.g., "...artificial intelligence (Artificial Intelligence Act)"
        short_match = re.search(r'\(([^)]+(?:Act|Regulation|Directive|Decision)[^)]*)\)\s*$', full_title)
        if short_match:
            result.short_title = short_match.group(1)

        # Try to determine CELEX from title
        celex_match = re.search(r'\((?:EU|EC|EEC)\)\s*(\d{4})/(\d+)', full_title)
        if celex_match:
            year = celex_match.group(1)
            number = celex_match.group(2)

            # Determine type code
            type_code = 'R'  # Regulation
            if 'Directive' in result.doc_type:
                type_code = 'L'
            elif 'Decision' in result.doc_type:
                type_code = 'D'

            result.celex = f"3{year}{type_code}{number.zfill(4)}"

    def _extract_recitals(self, root: ET.Element, result: ParsedLaw):
        """Extract recitals (whereas clauses)."""
        consid_group = root.find('.//GR.CONSID')
        if consid_group is None:
            return

        for consid in consid_group.findall('.//CONSID'):
            np = consid.find('.//NP')
            if np is None:
                continue

            # Get recital number
            no_p = np.findtext('NO.P', '')
            number = re.sub(r'[^\d]', '', no_p)  # Extract just digits

            # Get text
            txt = np.find('TXT')
            text = self._get_text(txt) if txt is not None else self._get_text(np)

            if number or text:
                result.recitals.append(Recital(
                    number=number or str(len(result.recitals) + 1),
                    text=text,
                    html=self._get_inner_html(consid)
                ))

    def _extract_articles(self, root: ET.Element, result: ParsedLaw):
        """Extract articles with their structure."""
        enacting = root.find('.//ENACTING.TERMS')
        if enacting is None:
            return

        current_chapter = ""
        current_chapter_title = ""
        current_section = ""
        current_section_title = ""

        # Process all elements in order
        for elem in enacting.iter():
            # Track divisions (chapters/sections)
            if elem.tag == 'DIVISION':
                title_el = elem.find('TITLE')
                if title_el is not None:
                    ti = title_el.findtext('.//TI/P', '')
                    sti = title_el.findtext('.//STI/P', '')

                    ti_upper = ti.upper()
                    if 'CHAPTER' in ti_upper:
                        current_chapter = ti
                        current_chapter_title = sti
                        current_section = ""
                        current_section_title = ""
                    elif 'SECTION' in ti_upper:
                        current_section = ti
                        current_section_title = sti

            # Extract articles
            if elem.tag == 'ARTICLE':
                article = self._parse_article(elem)
                if article:
                    article.chapter = current_chapter
                    article.chapter_title = current_chapter_title
                    article.section = current_section
                    article.section_title = current_section_title
                    result.articles.append(article)

    def _parse_article(self, elem: ET.Element) -> Optional[Article]:
        """Parse a single article element."""
        identifier = elem.get('IDENTIFIER', '')

        # Get article number from TI.ART
        ti_art = elem.findtext('TI.ART', '')
        number_match = re.search(r'Article\s+(\d+)', ti_art, re.IGNORECASE)
        number = number_match.group(1) if number_match else identifier

        # Get article title from STI.ART
        sti_art = elem.find('STI.ART')
        title = self._get_text(sti_art) if sti_art is not None else ''

        article = Article(
            number=number,
            identifier=identifier,
            title=title,
            html=self._get_inner_html(elem)
        )

        # Extract paragraphs
        for parag in elem.findall('.//PARAG'):
            para_id = parag.get('IDENTIFIER', '')
            no_parag = parag.findtext('NO.PARAG', '')

            # Get paragraph content
            alinea = parag.find('ALINEA')
            text = self._get_text(alinea) if alinea is not None else self._get_text(parag)

            article.paragraphs.append(Paragraph(
                number=no_parag.rstrip('.'),
                identifier=para_id,
                text=text,
                html=self._get_inner_html(parag)
            ))

        return article

    def _extract_annexes(self, root: ET.Element, result: ParsedLaw):
        """Extract annexes."""
        # Annexes are typically in separate files, but some documents embed them
        for annex in root.findall('.//ANNEX'):
            annex_id = annex.get('IDENTIFIER', '')

            # Get annex title
            ti = annex.find('.//TI')
            title = self._get_text(ti) if ti is not None else f"Annex {annex_id}"

            result.annexes.append(Annex(
                id=annex_id or str(len(result.annexes) + 1),
                title=title,
                html=self._get_inner_html(annex)
            ))

    def _extract_legal_basis(self, root: ET.Element, result: ParsedLaw):
        """Extract legal basis from visas."""
        visas = root.find('.//GR.VISA')
        if visas is None:
            return

        for visa in visas.findall('.//VISA'):
            text = self._get_text(visa)

            # Look for treaty references
            if 'Treaty' in text or 'TFEU' in text or 'TEU' in text:
                result.legal_basis.append(text)

            # Look for regulation/directive references
            ref_matches = re.findall(
                r'(?:Regulation|Directive|Decision)\s+\(?(?:EU|EC|EEC)?\)?\s*(?:No\s*)?(\d{4})/(\d+)',
                text,
                re.IGNORECASE
            )
            for year, number in ref_matches:
                result.citations.append(f"{year}/{number}")

    def _fallback_extraction(self, content: str, result: ParsedLaw):
        """Fallback regex-based extraction for malformed XML."""
        logger.warning("Using fallback regex extraction")

        # Extract title
        title_match = re.search(r'<TITLE>.*?<TI>(.*?)</TI>', content, re.DOTALL)
        if title_match:
            result.title = re.sub(r'<[^>]+>', ' ', title_match.group(1)).strip()

        # Extract recitals
        for match in re.finditer(r'<CONSID>.*?<NO\.P>\((\d+)\)</NO\.P>.*?<TXT>(.*?)</TXT>', content, re.DOTALL):
            number = match.group(1)
            text = re.sub(r'<[^>]+>', ' ', match.group(2)).strip()
            result.recitals.append(Recital(number=number, text=text))

        # Extract articles
        for match in re.finditer(r'<ARTICLE[^>]*IDENTIFIER="(\d+)"[^>]*>.*?<TI\.ART>Article\s+(\d+)</TI\.ART>', content, re.DOTALL):
            identifier = match.group(1)
            number = match.group(2)
            result.articles.append(Article(
                number=number,
                identifier=identifier,
                title="",
                html=""
            ))


def parse_formex_file(file_path: str | Path) -> ParsedLaw:
    """
    Convenience function to parse a Formex XML file.

    Args:
        file_path: Path to the Formex XML file

    Returns:
        ParsedLaw object containing extracted data
    """
    parser = FormexParser()
    return parser.parse_file(file_path)
