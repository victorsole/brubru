"""
Formex XML Parser for EU Laws

Parses EU legal documents in Formex XML format from LEG_2025-11 directory.
Extracts metadata including CELEX, title, date, legal basis, citations, and full text.

Formex is the EU Publications Office standard XML format used for
Official Journal publications.
"""

import logging
import re
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class FormexXMLParser:
    """
    Parser for Formex XML documents.

    Formex structure:
    - <ACT> root element
    - <BIB.INSTANCE> - bibliographic metadata
    - <TITLE> - document title
    - <PREAMBLE> - preamble with legal basis (VISA section)
    - <ENACTING.TERMS> - articles and legal content
    """

    def __init__(self):
        """Initialize parser"""
        self.namespaces = {
            'fmx': 'http://opoce',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }

    def parse_file(self, xml_path: str) -> Optional[Dict[str, Any]]:
        """
        Parse a Formex XML file and extract all metadata.

        Args:
            xml_path: Path to XML file

        Returns:
            Dictionary with extracted metadata or None if parsing fails
        """
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            metadata = {
                'xml_path': xml_path,
                'uuid': self._extract_uuid_from_path(xml_path),
                'celex': self._extract_celex(root),
                'doc_type': self._extract_doc_type(root),
                'title': self._extract_title(root),
                'date': self._extract_date(root),
                'oj_reference': self._extract_oj_reference(root),
                'legal_basis': self._extract_legal_basis(root),
                'citations': self._extract_citations(root),
                'subject_matter': self._extract_subject_matter(root),
                'articles': self._extract_articles(root),
                'full_text': self._extract_full_text(root),
                'metadata_extra': self._extract_extra_metadata(root)
            }

            logger.debug(f"Parsed {xml_path}: {metadata.get('title', 'Unknown')[:50]}")
            return metadata

        except Exception as e:
            logger.error(f"Failed to parse {xml_path}: {str(e)}")
            return None

    def _extract_uuid_from_path(self, xml_path: str) -> str:
        """
        Extract UUID from file path.

        Path structure: docs/LEG_2025-11/{UUID}/fmx4/filename.xml
        """
        path = Path(xml_path)
        # Get parent's parent (the UUID directory)
        uuid_dir = path.parent.parent.name
        return uuid_dir

    def _extract_celex(self, root: ET.Element) -> Optional[str]:
        """
        Extract CELEX number from document.

        CELEX format: 32019D1194 (year + type + sequential number)

        Extraction strategy:
        1. Look for CELEX in metadata
        2. Construct from NO.DOC element
        3. Parse from title
        """
        # Strategy 1: Check BIB.INSTANCE > NO.DOC
        no_doc = root.find('.//NO.DOC')
        if no_doc is not None:
            year = no_doc.find('YEAR')
            com = no_doc.find('COM')
            no_current = no_doc.find('NO.CURRENT')
            doc_format = no_doc.get('FORMAT', 'YN')

            if year is not None and no_current is not None:
                year_val = year.text
                num_val = no_current.text.zfill(4)  # Pad to 4 digits

                # Determine document type code from doc_type
                # This is a simplified mapping - full mapping requires more analysis
                doc_type_code = self._infer_celex_type_code(root)

                if doc_type_code:
                    celex = f"3{year_val}{doc_type_code}{num_val}"
                    return celex

        # Strategy 2: Try to extract from title/metadata
        # This is fallback and less reliable
        title = self._extract_title(root)
        if title:
            # Look for explicit CELEX mention
            celex_match = re.search(r'\b([0-9]{4}[A-Z][0-9]{4})\b', title)
            if celex_match:
                return '3' + celex_match.group(1)

        return None

    def _infer_celex_type_code(self, root: ET.Element) -> Optional[str]:
        """
        Infer CELEX document type code from document structure.

        Common codes:
        - R: Regulation
        - L: Directive
        - D: Decision
        - H: Recommendation
        - X: Opinion
        - E: Agreement
        """
        title = self._extract_title(root)
        if not title:
            return None

        title_upper = title.upper()

        # Check for document type in title
        if 'REGULATION' in title_upper:
            return 'R'
        elif 'DIRECTIVE' in title_upper:
            return 'L'
        elif 'DECISION' in title_upper:
            return 'D'
        elif 'RECOMMENDATION' in title_upper:
            return 'H'
        elif 'OPINION' in title_upper:
            return 'X'
        elif 'AGREEMENT' in title_upper or 'ACCORD' in title_upper:
            return 'E'

        return None

    def _extract_doc_type(self, root: ET.Element) -> str:
        """
        Extract document type from title.

        Examples:
        - "Commission Implementing Decision"
        - "Regulation (EU) 2019/1194"
        - "Directive 2016/680"
        """
        title = self._extract_title(root)
        if not title:
            return "Unknown"

        # Extract first part before document number
        # e.g., "Commission Implementing Decision (EU) 2019/1194" -> "Commission Implementing Decision"

        # Pattern: Look for text before (EU/EC) YYYY/NNNN or similar
        match = re.match(r'^(.+?)\s+\([EU|EC|EEC|EURATOM]+\)\s+\d{4}', title)
        if match:
            return match.group(1).strip()

        # Fallback: Extract until first number
        match = re.match(r'^([^0-9]+)', title)
        if match:
            doc_type = match.group(1).strip()
            # Remove trailing "of the European Parliament and of the Council" etc
            doc_type = re.sub(r'\s+of\s+(the\s+)?(European|Council|Commission).*$', '', doc_type, flags=re.IGNORECASE)
            return doc_type

        return "Unknown"

    def _extract_title(self, root: ET.Element) -> str:
        """
        Extract document title.

        Title is in <TITLE><TI><P> elements.
        Multiple <P> elements should be concatenated.
        """
        title_parts = []

        title_elem = root.find('.//TITLE/TI')
        if title_elem is not None:
            for p in title_elem.findall('P'):
                # Get text including nested elements
                text = self._get_element_text(p)
                if text:
                    title_parts.append(text.strip())

        title = ' '.join(title_parts)

        # Clean up multiple spaces
        title = re.sub(r'\s+', ' ', title)

        return title.strip()

    def _extract_date(self, root: ET.Element) -> Optional[str]:
        """
        Extract document date (ISO format YYYY-MM-DD).

        Date is in <BIB.INSTANCE><DATE ISO="YYYYMMDD">
        """
        date_elem = root.find('.//BIB.INSTANCE/DATE[@ISO]')
        if date_elem is not None:
            iso_date = date_elem.get('ISO')
            if iso_date and len(iso_date) == 8:
                # Convert YYYYMMDD to YYYY-MM-DD
                try:
                    year = iso_date[0:4]
                    month = iso_date[4:6]
                    day = iso_date[6:8]
                    return f"{year}-{month}-{day}"
                except:
                    pass

        return None

    def _extract_oj_reference(self, root: ET.Element) -> Optional[str]:
        """
        Extract Official Journal reference.

        Format: L 187/41 (Collection Number/Page)
        """
        bib = root.find('.//BIB.INSTANCE/DOCUMENT.REF')
        if bib is not None:
            coll = bib.find('COLL')
            no_oj = bib.find('NO.OJ')
            page_first = bib.find('PAGE.FIRST')

            if coll is not None and no_oj is not None:
                coll_text = coll.text
                no_text = no_oj.text
                page_text = page_first.text if page_first is not None else ''

                if page_text:
                    return f"{coll_text} {no_text}/{page_text}"
                else:
                    return f"{coll_text} {no_text}"

        return None

    def _extract_legal_basis(self, root: ET.Element) -> List[str]:
        """
        Extract legal basis (laws this document is based on).

        Legal basis is in <PREAMBLE><GR.VISA><VISA> elements.
        Look for references to other regulations/directives.
        """
        legal_basis = []

        # Find all VISA elements in preamble
        visa_elements = root.findall('.//PREAMBLE/GR.VISA/VISA')

        for visa in visa_elements:
            text = self._get_element_text(visa)
            if text:
                # Extract regulation/directive references
                # Pattern: "Regulation (EC) No 1907/2006"
                refs = re.findall(
                    r'(Regulation|Directive|Decision)\s+\((?:EC|EU|EEC|EURATOM)\)\s+No\.?\s*(\d{1,4}/\d{4})',
                    text,
                    re.IGNORECASE
                )

                for ref in refs:
                    doc_type, number = ref
                    legal_basis.append(f"{doc_type} {number}")

        return list(set(legal_basis))  # Remove duplicates

    def _extract_citations(self, root: ET.Element) -> List[str]:
        """
        Extract citations (references to other laws in the document).

        Look for CELEX numbers and regulation/directive references
        throughout the document.
        """
        citations = []

        # Get full text
        full_text = self._extract_full_text(root)

        if full_text:
            # Extract regulation/directive references
            # Pattern: "Regulation (EC) No 1907/2006"
            refs = re.findall(
                r'(Regulation|Directive|Decision)\s+\((?:EC|EU|EEC|EURATOM)\)\s+(?:No\.?\s*)?(\d{1,4}/\d{4})',
                full_text,
                re.IGNORECASE
            )

            for ref in refs:
                doc_type, number = ref
                citations.append(f"{number}")  # Just store the number

        # Remove duplicates and limit
        citations = list(set(citations))[:20]  # Max 20 citations

        return citations

    def _extract_subject_matter(self, root: ET.Element) -> List[str]:
        """
        Extract subject matter keywords from title and content.

        Uses simple keyword extraction from title.
        """
        keywords = []

        title = self._extract_title(root)
        if title:
            # Extract meaningful words (capitalized terms, technical terms)
            # Remove common words
            common_words = {
                'of', 'the', 'and', 'for', 'with', 'on', 'by', 'to', 'as',
                'in', 'at', 'from', 'or', 'an', 'a', 'is', 'are', 'was',
                'Commission', 'European', 'Parliament', 'Council', 'Union'
            }

            words = re.findall(r'\b[A-Z][a-z]+\b', title)
            keywords = [w for w in words if w not in common_words]

            # Also look for acronyms (all caps, 2-6 letters)
            acronyms = re.findall(r'\b[A-Z]{2,6}\b', title)
            keywords.extend(acronyms)

            # Remove duplicates
            keywords = list(set(keywords))[:10]  # Max 10 keywords

        return keywords

    def _extract_articles(self, root: ET.Element) -> List[Dict[str, Any]]:
        """
        Extract articles from ENACTING.TERMS section.

        Returns list of articles with their content.
        """
        articles = []

        # Find all ARTICLE elements
        article_elements = root.findall('.//ENACTING.TERMS/ARTICLE')

        for article in article_elements:
            article_id = article.get('IDENTIFIER', '')

            # Extract title
            title_elem = article.find('TI.ART')
            title = self._get_element_text(title_elem) if title_elem is not None else ''

            # Extract paragraphs
            paragraphs = []
            for parag in article.findall('.//PARAG'):
                parag_id = parag.get('IDENTIFIER', '')
                parag_text = self._get_element_text(parag)
                if parag_text:
                    paragraphs.append({
                        'id': parag_id,
                        'text': parag_text
                    })

            # Extract alineas (single article without paragraphs)
            for alinea in article.findall('ALINEA'):
                alinea_text = self._get_element_text(alinea)
                if alinea_text:
                    paragraphs.append({
                        'id': '',
                        'text': alinea_text
                    })

            if title or paragraphs:
                articles.append({
                    'id': article_id,
                    'title': title,
                    'paragraphs': paragraphs
                })

        return articles

    def _extract_full_text(self, root: ET.Element) -> str:
        """
        Extract full text content from document.

        Extracts text from:
        - Title
        - Preamble (recitals)
        - Enacting terms (articles)
        """
        text_parts = []

        # Title
        title = self._extract_title(root)
        if title:
            text_parts.append(title)

        # Preamble recitals
        recitals = root.findall('.//PREAMBLE/GR.CONSID/CONSID')
        for recital in recitals:
            recital_text = self._get_element_text(recital)
            if recital_text:
                text_parts.append(recital_text)

        # Articles
        articles = root.findall('.//ENACTING.TERMS/ARTICLE')
        for article in articles:
            article_text = self._get_element_text(article)
            if article_text:
                text_parts.append(article_text)

        full_text = '\n\n'.join(text_parts)

        # Clean up
        full_text = re.sub(r'\s+', ' ', full_text)
        full_text = re.sub(r'\n\s*\n', '\n\n', full_text)

        return full_text.strip()

    def _extract_extra_metadata(self, root: ET.Element) -> Dict[str, Any]:
        """
        Extract additional metadata.

        Returns dictionary with optional fields like:
        - EEA relevance
        - Language
        - Pages
        """
        extra = {}

        # Check for EEA relevance
        eea_elem = root.find('.//BIB.INSTANCE/EEA')
        if eea_elem is not None:
            extra['eea_relevant'] = True

        # Language
        lg_elem = root.find('.//BIB.INSTANCE/LG.DOC')
        if lg_elem is not None:
            extra['language'] = lg_elem.text

        # Page count
        page_first = root.find('.//BIB.INSTANCE/PAGE.FIRST')
        page_last = root.find('.//BIB.INSTANCE/PAGE.LAST')
        if page_first is not None and page_last is not None:
            try:
                extra['page_first'] = int(page_first.text)
                extra['page_last'] = int(page_last.text)
                extra['page_count'] = extra['page_last'] - extra['page_first'] + 1
            except:
                pass

        return extra

    def _get_element_text(self, elem: Optional[ET.Element]) -> str:
        """
        Get all text content from element including nested elements.

        Handles nested formatting tags like <HT>, <QUOT.START>, etc.
        """
        if elem is None:
            return ""

        # Get text including tail of all descendants
        text_parts = []

        # Element's own text
        if elem.text:
            text_parts.append(elem.text)

        # Recurse through children
        for child in elem:
            child_text = self._get_element_text(child)
            if child_text:
                text_parts.append(child_text)

            # Tail text after child element
            if child.tail:
                text_parts.append(child.tail)

        text = ''.join(text_parts)

        # Clean up
        text = re.sub(r'\s+', ' ', text)

        return text.strip()


# Global singleton
_parser: Optional[FormexXMLParser] = None


def get_xml_parser() -> FormexXMLParser:
    """Get global XML parser instance"""
    global _parser
    if _parser is None:
        _parser = FormexXMLParser()
    return _parser
