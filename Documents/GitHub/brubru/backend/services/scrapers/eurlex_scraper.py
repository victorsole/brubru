"""
EUR-Lex Scraper

Scrapes official EU legal documents, consolidated legislation, and case law
from eur-lex.europa.eu
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from .base_scraper import BaseScraper, ScraperError
from ...schemas.scrapers.scraper_schemas import LegislativeDocument, DocumentType


class EURLexScraper(BaseScraper):
    """
    Scraper for EUR-Lex legislative database.

    Key Features:
    - Search legislation by CELEX number
    - Retrieve document text in multiple formats (HTML, PDF, XML)
    - Get consolidated versions of amended legislation
    - Access case law and court decisions
    - Download Akoma Ntoso XML for amendable documents
    """

    SEARCH_URL = "https://eur-lex.europa.eu/search.html"
    DOCUMENT_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/"
    SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"

    # CELEX pattern: Year + Sector + Number (e.g., 32024R1234)
    CELEX_PATTERN = re.compile(r'[0-9]{5}[A-Z][0-9]{4}')

    def __init__(self, **kwargs):
        super().__init__(
            base_url="https://eur-lex.europa.eu",
            name="EUR-Lex",
            rate_limit_delay=1.5,
            **kwargs
        )

    async def get_document_by_celex(self, celex_number: str) -> LegislativeDocument:
        """
        Retrieve document by CELEX number.

        Args:
            celex_number: CELEX identifier (e.g., '32016R0679' for GDPR)

        Returns:
            LegislativeDocument object with full metadata

        Raises:
            ScraperError: If CELEX number is invalid or document not found
        """
        # Validate CELEX format
        if not self.CELEX_PATTERN.match(celex_number):
            raise ScraperError(f"Invalid CELEX number format: {celex_number}")

        # Construct document URL
        url = f"{self.DOCUMENT_URL}?uri=CELEX:{celex_number}"
        html = await self._fetch(url)
        soup = self._parse_html(html)

        # Extract title
        title_elem = soup.find('h1', class_='title')
        title = title_elem.get_text(strip=True) if title_elem else "Unknown Title"

        # Extract document type from CELEX
        doc_type = self._parse_document_type_from_celex(celex_number)

        # Extract publication date
        date_published = None
        date_elem = soup.find('dd', class_='doc-date')
        if date_elem:
            date_str = date_elem.get_text(strip=True)
            try:
                date_published = datetime.strptime(date_str, "%d/%m/%Y")
            except ValueError:
                pass

        # Extract subjects
        subjects = []
        subject_section = soup.find('div', {'id': 'subjectMatters'})
        if subject_section:
            for subject in subject_section.find_all('a'):
                subjects.append(subject.get_text(strip=True))

        # Get various format URLs
        pdf_url = f"{self.DOCUMENT_URL}PDF/?uri=CELEX:{celex_number}"
        xml_url = f"{self.DOCUMENT_URL}XML/?uri=CELEX:{celex_number}"
        html_url = url

        # Extract text content
        text_content = self._extract_document_text(soup)

        return LegislativeDocument(
            source=self.name,
            source_url=url,
            celex_number=celex_number,
            document_id=celex_number,
            title=title,
            document_type=doc_type,
            date_published=date_published,
            subjects=subjects,
            text_content=text_content,
            html_url=html_url,
            pdf_url=pdf_url,
            xml_url=xml_url,
        )

    def _parse_document_type_from_celex(self, celex: str) -> DocumentType:
        """
        Extract document type from CELEX number.

        CELEX format: YYYYY T NNNN
        Where T is sector/type:
        - R = Regulation
        - L = Directive
        - D = Decision
        - C = Communication
        """
        if len(celex) >= 6:
            type_code = celex[5]
            type_mapping = {
                'R': DocumentType.REGULATION,
                'L': DocumentType.DIRECTIVE,
                'D': DocumentType.DECISION,
                'C': DocumentType.COMMUNICATION,
            }
            return type_mapping.get(type_code, DocumentType.OTHER)

        return DocumentType.OTHER

    def _extract_document_text(self, soup) -> Optional[str]:
        """Extract clean text content from document HTML"""
        content_div = soup.find('div', {'id': 'text'})
        if content_div:
            # Remove script and style elements
            for script in content_div(["script", "style"]):
                script.decompose()

            # Get text
            text = content_div.get_text(separator='\n', strip=True)
            return text

        return None

    async def search_legislation(
        self,
        query: str,
        document_type: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        author: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search EUR-Lex for legislation.

        Args:
            query: Search query text
            document_type: Filter by type (e.g., 'regulation', 'directive')
            date_from: Start date for date range
            date_to: End date for date range
            author: Filter by authoring institution
            limit: Maximum results to return

        Returns:
            List of search results with document metadata
        """
        # Build search parameters
        params = {
            'text': query,
            'qid': '1',
            'type': 'quick',
            'lang': 'en',
        }

        if document_type:
            params['FM_CODED'] = document_type.upper()

        if date_from:
            params['DD_FROM'] = date_from.strftime('%Y%m%d')

        if date_to:
            params['DD_TO'] = date_to.strftime('%Y%m%d')

        if author:
            params['AUTHOR'] = author

        # Execute search
        html = await self._fetch(self.SEARCH_URL, params=params)
        soup = self._parse_html(html)

        # Parse search results
        results = []
        result_items = soup.find_all('div', class_='SearchResult')[:limit]

        for item in result_items:
            try:
                title_elem = item.find('a', class_='title')
                celex_elem = item.find('span', class_='celexNbr')

                if title_elem and celex_elem:
                    results.append({
                        'title': title_elem.get_text(strip=True),
                        'celex_number': celex_elem.get_text(strip=True),
                        'url': self._make_absolute_url(title_elem['href']),
                    })
            except Exception:
                continue

        return results

    async def get_consolidated_version(self, celex_number: str) -> Optional[str]:
        """
        Get consolidated (amended) version of legislation.

        Args:
            celex_number: CELEX of original act

        Returns:
            CELEX of consolidated version, or None if not available
        """
        url = f"{self.DOCUMENT_URL}?uri=CELEX:{celex_number}&qid=consolidated"
        html = await self._fetch(url)
        soup = self._parse_html(html)

        # Look for consolidated version link
        consolidated_link = soup.find('a', string=re.compile(r'Consolidated'))
        if consolidated_link and 'href' in consolidated_link.attrs:
            # Extract CELEX from consolidated URL
            celex_match = self.CELEX_PATTERN.search(consolidated_link['href'])
            if celex_match:
                return celex_match.group(0)

        return None

    async def download_akoma_ntoso_xml(self, celex_number: str) -> Optional[str]:
        """
        Download Akoma Ntoso XML format (for amendable documents).

        Args:
            celex_number: CELEX identifier

        Returns:
            XML content as string, or None if not available
        """
        url = f"{self.DOCUMENT_URL}XML/?uri=CELEX:{celex_number}&format=akn"

        try:
            xml_content = await self._fetch(url)
            return xml_content
        except ScraperError:
            # Not all documents have Akoma Ntoso format
            return None

    # Implement abstract methods

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search EUR-Lex database"""
        return await self.search_legislation(query, **kwargs)

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """Get document by CELEX number"""
        doc = await self.get_document_by_celex(document_id)
        return doc.dict()

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recently published legislation"""
        # Search recent documents
        date_from = datetime.now().replace(day=1)  # Current month
        return await self.search_legislation(
            query="*",
            date_from=date_from,
            limit=limit
        )
