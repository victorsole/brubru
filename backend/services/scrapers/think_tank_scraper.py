"""
European Parliament Think Tank Scraper

PHASE 1 UPGRADE: Full Content Extraction
- RSS feeds for EPRS publications (primary)
- PDF download and text extraction
- Entity extraction (CELEX, procedures, MEPs)
- Document structure parsing
- Enriched publication objects with full content

PHASE 4 UPGRADE: Integrated with RSS clients
- Document type feeds (briefings, studies, at-a-glance)
- Web scraping as fallback

Scrapes European Parliament Research Service publications, briefings,
studies, and in-depth analyses
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from pathlib import Path

from .base_scraper import BaseScraper
from services.api_clients.think_tank_rss_client import ThinkTankRSSClient
from services.document_processing import EPRSContentEnricher, PDFProcessor
from schemas.scrapers.scraper_schemas import EPRSPublication, EPRSExtractionResult

logger = logging.getLogger(__name__)


class ThinkTankScraper(BaseScraper):
    """
    Scraper for European Parliament Think Tank (EPRS).

    PHASE 1 UPGRADE: Full Content Extraction
    - Download and extract PDF content
    - Entity extraction (CELEX, procedures, MEPs, committees)
    - Document structure parsing
    - Enriched EPRSPublication objects

    PHASE 4 UPGRADE:
    - Primary: RSS feeds for all publication types
    - Categorized feeds (briefings, studies, at-a-glance)
    - Real-time monitoring for new research
    - Fallback: Web scraping

    Key Features:
    - EPRS briefings and policy papers
    - In-depth analysis documents
    - At-a-glance summaries
    - European Parliament studies
    - Full-text extraction and analysis
    - Keyword-based search via RSS filtering
    """

    def __init__(
        self,
        enable_full_extraction: bool = True,
        download_dir: Optional[Path] = None,
        **kwargs
    ):
        """
        Initialize Think Tank Scraper.

        Args:
            enable_full_extraction: Enable PDF download and content extraction
            download_dir: Directory for downloaded PDFs
            **kwargs: Additional arguments for BaseScraper
        """
        super().__init__(
            base_url="https://www.europarl.europa.eu/thinktank/en/home",
            name="ThinkTank",
            rate_limit_delay=2.0,
            **kwargs
        )

        # PHASE 4: Initialize RSS client
        self.rss_client = ThinkTankRSSClient()
        self.use_api = True

        # PHASE 1: Initialize content extraction components
        self.enable_full_extraction = enable_full_extraction
        if enable_full_extraction:
            self.pdf_processor = PDFProcessor(download_dir=download_dir)
            self.enricher = EPRSContentEnricher(pdf_processor=self.pdf_processor)
            logger.info("Think Tank Scraper initialized with FULL CONTENT EXTRACTION enabled")
        else:
            self.pdf_processor = None
            self.enricher = None
            logger.info("Think Tank Scraper initialized with RSS client only")

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Search Think Tank publications.

        PHASE 4: RSS feeds with keyword filtering

        Args:
            query: Search query
            **kwargs: Additional parameters (publication_type, date_from)

        Returns:
            List of matching publications
        """
        if self.use_api:
            try:
                logger.info(f"Searching Think Tank publications: {query}")
                # Fetch recent publications
                publications = await self.rss_client.get_latest_publications(hours=168)  # 1 week

                # Filter by query
                results = [
                    item for item in publications
                    if query.lower() in item['title'].lower() or
                       query.lower() in item.get('summary', '').lower()
                ]

                # Apply additional filters
                if 'publication_type' in kwargs:
                    results = [
                        item for item in results
                        if item.get('type') == kwargs['publication_type']
                    ]

                return results
            except Exception as e:
                logger.error(f"Think Tank search failed: {str(e)}")

        return []

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Get Think Tank document by ID.

        Args:
            document_id: Document identifier

        Returns:
            Document data
        """
        logger.info(f"Fetching Think Tank document: {document_id}")
        # Would use web scraping or direct URL access
        return {}

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get latest Think Tank publications via RSS.

        PHASE 4: RSS feeds

        Args:
            limit: Maximum results

        Returns:
            Latest publications
        """
        if self.use_api:
            try:
                logger.info("Fetching latest Think Tank updates via RSS")
                publications = await self.rss_client.get_latest_publications(hours=24)
                return publications[:limit]
            except Exception as e:
                logger.error(f"RSS fetch failed: {str(e)}")

        return []

    async def get_briefings(
        self,
        hours: int = 168,
        keyword: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        PHASE 4: New method - Get EPRS briefings via RSS

        Args:
            hours: Time window in hours
            keyword: Optional keyword filter

        Returns:
            List of briefings
        """
        if not self.use_api:
            raise NotImplementedError("RSS feeds require API client")

        try:
            logger.info("Fetching Think Tank briefings")
            briefings = await self.rss_client.get_briefings(hours)

            if keyword:
                briefings = [
                    b for b in briefings
                    if keyword.lower() in b['title'].lower() or
                       keyword.lower() in b.get('summary', '').lower()
                ]

            return briefings
        except Exception as e:
            logger.error(f"Failed to fetch briefings: {str(e)}")
            return []

    async def get_at_a_glance(
        self,
        hours: int = 168
    ) -> List[Dict[str, Any]]:
        """
        PHASE 4: New method - Get 'At a glance' summaries via RSS

        Args:
            hours: Time window in hours

        Returns:
            List of at-a-glance summaries
        """
        if not self.use_api:
            raise NotImplementedError("RSS feeds require API client")

        try:
            logger.info("Fetching 'At a glance' summaries")
            summaries = await self.rss_client.get_at_a_glance(hours)
            return summaries
        except Exception as e:
            logger.error(f"Failed to fetch at-a-glance summaries: {str(e)}")
            return []

    async def get_in_depth_analysis(
        self,
        hours: int = 168
    ) -> List[Dict[str, Any]]:
        """
        PHASE 4: New method - Get in-depth analysis documents via RSS

        Args:
            hours: Time window in hours

        Returns:
            List of in-depth analyses
        """
        if not self.use_api:
            raise NotImplementedError("RSS feeds require API client")

        try:
            logger.info("Fetching in-depth analyses")
            analyses = await self.rss_client.get_in_depth_analysis(hours)
            return analyses
        except Exception as e:
            logger.error(f"Failed to fetch in-depth analyses: {str(e)}")
            return []

    async def get_studies(
        self,
        hours: int = 168,
        policy_area: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        PHASE 4: New method - Get European Parliament studies via RSS

        Args:
            hours: Time window in hours
            policy_area: Optional policy area filter

        Returns:
            List of studies
        """
        if not self.use_api:
            raise NotImplementedError("RSS feeds require API client")

        try:
            logger.info("Fetching EP studies")
            studies = await self.rss_client.get_studies(hours)

            if policy_area:
                studies = [
                    s for s in studies
                    if policy_area.lower() in s.get('categories', [])
                ]

            return studies
        except Exception as e:
            logger.error(f"Failed to fetch studies: {str(e)}")
            return []

    async def search_by_keyword(
        self,
        keyword: str,
        publication_types: Optional[List[str]] = None,
        hours: int = 720  # 30 days default
    ) -> List[Dict[str, Any]]:
        """
        PHASE 4: New method - Search all publication types by keyword

        Args:
            keyword: Keyword to search for
            publication_types: Filter by types (briefing, study, at_a_glance, analysis)
            hours: Time window in hours

        Returns:
            List of matching publications
        """
        if not self.use_api:
            raise NotImplementedError("RSS feeds require API client")

        try:
            logger.info(f"Searching Think Tank by keyword: {keyword}")
            all_publications = await self.rss_client.get_latest_publications(hours)

            # Filter by keyword
            results = [
                pub for pub in all_publications
                if keyword.lower() in pub['title'].lower() or
                   keyword.lower() in pub.get('summary', '').lower()
            ]

            # Filter by publication types if specified
            if publication_types:
                results = [
                    pub for pub in results
                    if pub.get('type') in publication_types
                ]

            return results
        except Exception as e:
            logger.error(f"Keyword search failed: {str(e)}")
            return []

    async def close(self):
        """Close RSS client connections"""
        if hasattr(self, 'rss_client'):
            await self.rss_client.close()
            logger.info("Closed Think Tank RSS client")

    # ========================================================================
    # PHASE 1: FULL CONTENT EXTRACTION METHODS
    # ========================================================================

    async def get_publication_with_full_content(
        self,
        publication_url: str,
        pdf_url: Optional[str] = None,
        title: Optional[str] = None
    ) -> EPRSExtractionResult:
        """
        Get single EPRS publication with full PDF content extraction.

        PHASE 1: This is the core method for enriching EPRS publications.

        Args:
            publication_url: HTML page URL
            pdf_url: PDF download URL (optional, will try to find it)
            title: Publication title (optional, will extract from page)

        Returns:
            EPRSExtractionResult with enriched publication

        Example:
            scraper = ThinkTankScraper()
            result = await scraper.get_publication_with_full_content(
                publication_url="https://epthinktank.eu/2024/.../ai-act/",
                pdf_url="https://.../document.pdf"
            )

            print(f"Extracted {result.publication.word_count} words")
            print(f"Found {len(result.publication.related_celex_numbers)} CELEX numbers")
        """
        if not self.enable_full_extraction:
            raise ValueError(
                "Full extraction not enabled. Initialize with enable_full_extraction=True"
            )

        logger.info(f"Fetching publication with full content: {publication_url}")

        # If no PDF URL provided, try to find it
        if not pdf_url:
            pdf_url = await self._find_pdf_url(publication_url)

        if not pdf_url:
            raise ValueError(f"No PDF URL found for {publication_url}")

        # If no title, extract from URL or use placeholder
        if not title:
            title = self._extract_title_from_url(publication_url)

        # Create and enrich publication
        publication = await self.enricher.enrich_from_rss(
            title=title,
            link=publication_url,
            pdf_url=pdf_url
        )

        result = await self.enricher.enrich_publication(
            publication,
            download_pdf=True,
            extract_entities=True
        )

        logger.info(
            f"Publication enriched: {result.publication.title} - "
            f"{result.publication.word_count} words, "
            f"quality={result.extraction_quality}"
        )

        return result

    async def get_latest_publications_enriched(
        self,
        hours: int = 168,
        limit: int = 10,
        publication_type: Optional[str] = None
    ) -> List[EPRSExtractionResult]:
        """
        Get latest EPRS publications with FULL CONTENT EXTRACTION.

        PHASE 1: This method downloads PDFs and extracts all content.

        Args:
            hours: Time window in hours (default 7 days)
            limit: Maximum number of publications to enrich
            publication_type: Filter by type (briefings, studies, etc.)

        Returns:
            List of EPRSExtractionResult with enriched publications

        Example:
            scraper = ThinkTankScraper()
            results = await scraper.get_latest_publications_enriched(
                hours=24,
                limit=5,
                publication_type="briefings"
            )

            for result in results:
                pub = result.publication
                print(f"{pub.title}: {pub.word_count} words, "
                      f"{len(pub.related_celex_numbers)} CELEX refs")
        """
        if not self.enable_full_extraction:
            raise ValueError(
                "Full extraction not enabled. Initialize with enable_full_extraction=True"
            )

        logger.info(
            f"Fetching latest {limit} publications with full extraction "
            f"(type={publication_type or 'all'})"
        )

        # Get RSS entries
        publications = await self.rss_client.get_latest_publications(
            days=hours // 24,
            publication_type=publication_type
        )

        # Limit results
        publications = publications[:limit]

        enriched_results = []

        for pub_data in publications:
            try:
                # Extract PDF URL from enclosures or link
                pdf_url = self._extract_pdf_url_from_rss(pub_data)

                if not pdf_url:
                    logger.warning(f"No PDF URL for: {pub_data.get('title', 'Unknown')}")
                    continue

                # Create base publication from RSS
                publication = await self.enricher.enrich_from_rss(
                    title=pub_data.get('title', ''),
                    link=pub_data.get('link', ''),
                    pdf_url=pdf_url,
                    published_date=pub_data.get('published'),
                    summary=pub_data.get('summary'),
                    categories=pub_data.get('categories', [])
                )

                # Enrich with full content
                result = await self.enricher.enrich_publication(
                    publication,
                    download_pdf=True,
                    extract_entities=True
                )

                enriched_results.append(result)

                logger.info(
                    f"Enriched: {result.publication.title} "
                    f"({result.publication.word_count} words, "
                    f"quality={result.extraction_quality})"
                )

            except Exception as e:
                logger.error(
                    f"Failed to enrich publication {pub_data.get('title', 'Unknown')}: {str(e)}"
                )
                continue

        logger.info(f"Enriched {len(enriched_results)} publications successfully")
        return enriched_results

    async def search_with_full_content(
        self,
        keyword: str,
        hours: int = 720,
        limit: int = 5
    ) -> List[EPRSExtractionResult]:
        """
        Search EPRS publications by keyword and extract full content.

        PHASE 1: Search + Full PDF extraction

        Args:
            keyword: Search keyword
            hours: Time window (default 30 days)
            limit: Max results to fully extract

        Returns:
            List of EPRSExtractionResult

        Example:
            results = await scraper.search_with_full_content(
                keyword="artificial intelligence",
                limit=3
            )

            for result in results:
                print(f"{result.publication.title}")
                print(f"CELEX: {result.publication.related_celex_numbers}")
                print(f"Key findings: {result.publication.key_findings}")
        """
        if not self.enable_full_extraction:
            raise ValueError(
                "Full extraction not enabled. Initialize with enable_full_extraction=True"
            )

        logger.info(f"Searching with full extraction: '{keyword}'")

        # Search via RSS
        search_results = await self.rss_client.search_by_keyword(
            keyword=keyword,
            days=hours // 24
        )

        # Limit results
        search_results = search_results[:limit]

        enriched_results = []

        for pub_data in search_results:
            try:
                pdf_url = self._extract_pdf_url_from_rss(pub_data)

                if not pdf_url:
                    logger.warning(f"No PDF for: {pub_data.get('title', 'Unknown')}")
                    continue

                publication = await self.enricher.enrich_from_rss(
                    title=pub_data.get('title', ''),
                    link=pub_data.get('link', ''),
                    pdf_url=pdf_url,
                    published_date=pub_data.get('published'),
                    summary=pub_data.get('summary'),
                    categories=pub_data.get('categories', [])
                )

                result = await self.enricher.enrich_publication(publication)
                enriched_results.append(result)

                logger.info(f"Enriched search result: {result.publication.title}")

            except Exception as e:
                logger.error(f"Failed to enrich: {str(e)}")
                continue

        return enriched_results

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    # Mapping from EPRS document short codes to RegData folder names
    EPRS_CODE_TO_FOLDER = {
        "ATA": "ATAG",    # At a Glance
        "BRI": "BRIE",    # Briefing
        "IDA": "IDAN",    # In-Depth Analysis
        "STU": "STUD",    # Study
    }

    def _extract_pdf_url_from_rss(self, pub_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract PDF URL from RSS entry data.

        Checks:
        1. Direct 'pdf_url' field
        2. Link ending in .pdf
        3. Enclosures
        4. europarl.europa.eu document reference in RSS content
        5. Scrape blog post page for europarl link (async fallback)
        """
        # Check direct pdf_url field
        if 'pdf_url' in pub_data:
            return pub_data['pdf_url']

        # Check if link is a PDF
        link = pub_data.get('link', '')
        if link.endswith('.pdf'):
            return link

        # Check enclosures (RSS media attachments)
        if 'enclosures' in pub_data:
            for enclosure in pub_data['enclosures']:
                if enclosure.get('type', '').startswith('application/pdf'):
                    return enclosure.get('url')

        # Parse europarl document reference from RSS content:encoded
        # The epthinktank.eu blog posts embed links like:
        #   href="https://www.europarl.europa.eu/thinktank/en/document/EPRS_ATA(2026)782665"
        content = pub_data.get('content', '')
        pdf_url = self._extract_pdf_from_europarl_ref(content)
        if pdf_url:
            return pdf_url

        # Also check summary (sometimes contains the link)
        summary = pub_data.get('summary', '')
        pdf_url = self._extract_pdf_from_europarl_ref(summary)
        if pdf_url:
            return pdf_url

        return None

    def _extract_pdf_from_europarl_ref(self, html_content: str) -> Optional[str]:
        """
        Extract PDF URL from europarl.europa.eu document reference in HTML.

        Parses links like:
            https://www.europarl.europa.eu/thinktank/en/document/EPRS_ATA(2026)782665

        Constructs PDF URL:
            https://www.europarl.europa.eu/RegData/etudes/ATAG/2026/782665/EPRS_ATA(2026)782665_EN.pdf

        Returns:
            PDF URL or None
        """
        if not html_content:
            return None

        # Pattern: EPRS_{CODE}({YEAR}){ID}
        # e.g., EPRS_ATA(2026)782665, EPRS_BRI(2025)123456
        match = re.search(
            r'(EPRS_([A-Z]{3})\((\d{4})\)(\d+))',
            html_content
        )
        if not match:
            return None

        full_code = match.group(1)   # EPRS_ATA(2026)782665
        short_code = match.group(2)  # ATA
        year = match.group(3)        # 2026
        doc_id = match.group(4)      # 782665

        folder = self.EPRS_CODE_TO_FOLDER.get(short_code)
        if not folder:
            logger.warning(f"Unknown EPRS code '{short_code}' in {full_code}")
            return None

        pdf_url = (
            f"https://www.europarl.europa.eu/RegData/etudes/"
            f"{folder}/{year}/{doc_id}/{full_code}_EN.pdf"
        )
        logger.debug(f"Constructed PDF URL from europarl ref: {pdf_url}")
        return pdf_url

    async def _find_pdf_url(self, page_url: str) -> Optional[str]:
        """
        Find PDF URL by scraping the publication page.

        Strategy:
        1. Fetch blog post HTML
        2. Look for europarl.europa.eu document reference -> construct PDF URL
        3. Fallback: look for any .pdf link

        Args:
            page_url: HTML page URL

        Returns:
            PDF URL or None
        """
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(page_url) as response:
                    html = await response.text()

                    # Try europarl document reference first
                    pdf_url = self._extract_pdf_from_europarl_ref(html)
                    if pdf_url:
                        return pdf_url

                    # Fallback: find any .pdf link
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, 'html.parser')

                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        if href.endswith('.pdf'):
                            if href.startswith('http'):
                                return href
                            else:
                                return f"https://epthinktank.eu{href}"

        except Exception as e:
            logger.error(f"Failed to find PDF URL from page {page_url}: {str(e)}")

        return None

    def _extract_title_from_url(self, url: str) -> str:
        """Extract title from URL slug"""
        # Extract last part of URL and clean it
        import re
        slug = url.rstrip('/').split('/')[-1]
        # Replace hyphens with spaces and capitalize
        title = slug.replace('-', ' ').replace('_', ' ').title()
        return title
