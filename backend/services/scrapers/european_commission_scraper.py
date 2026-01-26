"""
European Commission Scraper

Scrapes the European Commission website for:
- Press releases and news
- Policy announcements
- Commissioner speeches and statements
- Initiative launches

Sources:
- https://ec.europa.eu/commission/presscorner/home/en
- https://commission.europa.eu/news_en
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, ScraperError
from schemas.scrapers.base_schemas import (
    ScrapedNewsItem,
    ScrapedDocument,
    ScrapedSearchResult,
    DataSource,
    DocumentType,
)

logger = logging.getLogger(__name__)


class EuropeanCommissionScraper(BaseScraper):
    """
    Scraper for European Commission press releases and news.

    Provides access to:
    - Press corner releases
    - News articles
    - Commissioner speeches
    - Policy announcements

    Example usage:
        scraper = EuropeanCommissionScraper()
        releases = await scraper.get_press_releases(limit=20)
        news = await scraper.get_latest_updates()
        search_results = await scraper.search("digital markets act")
    """

    # EC URLs
    PRESS_CORNER = "https://ec.europa.eu/commission/presscorner"
    NEWS_URL = "https://commission.europa.eu/news_en"
    SEARCH_URL = "https://ec.europa.eu/commission/presscorner/api/search"

    # Content types
    PRESS_RELEASE = "IP"  # Press release
    STATEMENT = "STATEMENT"
    SPEECH = "SPEECH"
    MEMO = "MEMO"
    QANDA = "QANDA"  # Questions and Answers

    def __init__(self, **kwargs):
        super().__init__(
            base_url="https://ec.europa.eu/commission/presscorner",
            name="EuropeanCommission",
            rate_limit_delay=2.0,
            **kwargs
        )

    async def search(
        self,
        query: str,
        content_type: Optional[str] = None,
        limit: int = 20,
        **kwargs
    ) -> List[ScrapedSearchResult]:
        """
        Search EC press corner for content.

        Args:
            query: Search term
            content_type: Filter by type (IP, STATEMENT, SPEECH, MEMO, QANDA)
            limit: Maximum results

        Returns:
            List of search results
        """
        logger.info(f"Searching EC for: {query}")

        # Try the press corner search
        search_url = f"{self.PRESS_CORNER}/home/en"
        params = {
            'keywords': query,
            'dotyp': content_type or '',
        }

        try:
            html = await self._fetch(search_url, params=params)
            soup = self._parse_html(html)

            results = []

            # Parse search results
            for item in soup.select('.ecl-content-block, .news-item, .search-result'):
                title_elem = item.select_one('h2 a, h3 a, .title a, a.ecl-link')
                date_elem = item.select_one('.date, time, .ecl-date-block')
                excerpt_elem = item.select_one('.summary, .description, p')
                type_elem = item.select_one('.type, .category, .document-type')

                if title_elem:
                    url = title_elem.get('href', '')
                    if url and not url.startswith('http'):
                        url = self._make_absolute_url(url)

                    # Parse date
                    date = None
                    if date_elem:
                        date_text = date_elem.get_text(strip=True)
                        date = self._parse_date(date_text)

                    # Determine document type
                    doc_type = DocumentType.PRESS_RELEASE
                    if type_elem:
                        type_text = type_elem.get_text(strip=True).upper()
                        if 'SPEECH' in type_text:
                            doc_type = DocumentType.SPEECH
                        elif 'STATEMENT' in type_text:
                            doc_type = DocumentType.PRESS_RELEASE

                    result = ScrapedSearchResult(
                        id=url.split('/')[-1] if url else '',
                        title=title_elem.get_text(strip=True),
                        url=url,
                        snippet=excerpt_elem.get_text(strip=True)[:300] if excerpt_elem else None,
                        source=DataSource.EUROPEAN_COMMISSION,
                        document_type=doc_type,
                        date=date,
                    )
                    results.append(result)

            return results[:limit]

        except Exception as e:
            logger.error(f"EC search failed: {e}")
            return []

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Get a specific press release or document.

        Args:
            document_id: Document reference (e.g., IP/24/1234)

        Returns:
            Document details
        """
        doc = await self.get_press_release(document_id)
        if doc:
            return doc.model_dump()
        return {}

    async def get_latest_updates(self, limit: int = 10) -> List[ScrapedNewsItem]:
        """
        Get latest news and press releases.

        Args:
            limit: Maximum items to return

        Returns:
            List of news items
        """
        return await self.get_press_releases(limit=limit)

    async def get_press_releases(
        self,
        limit: int = 20,
        content_type: Optional[str] = None,
        commissioner: Optional[str] = None,
    ) -> List[ScrapedNewsItem]:
        """
        Get recent press releases from Press Corner.

        Args:
            limit: Maximum releases to fetch
            content_type: Filter by type (IP, STATEMENT, SPEECH)
            commissioner: Filter by Commissioner name

        Returns:
            List of press releases
        """
        logger.info(f"Fetching EC press releases (limit={limit})")

        url = f"{self.PRESS_CORNER}/home/en"
        params = {}
        if content_type:
            params['dotyp'] = content_type

        try:
            html = await self._fetch(url, params=params)
            soup = self._parse_html(html)

            releases = []

            # Parse press release items
            for item in soup.select('.ecl-content-block, .news-card, article.press-release'):
                release = self._parse_press_release_card(item)
                if release:
                    releases.append(release)

            # Also try the latest news section
            for item in soup.select('.latest-news li, .news-list-item'):
                release = self._parse_press_release_card(item)
                if release and release.title not in [r.title for r in releases]:
                    releases.append(release)

            logger.info(f"Found {len(releases)} press releases")
            return releases[:limit]

        except Exception as e:
            logger.error(f"Failed to fetch press releases: {e}")
            return []

    async def get_press_release(self, reference: str) -> Optional[ScrapedNewsItem]:
        """
        Get a specific press release by reference.

        Args:
            reference: Press release reference (e.g., "IP/24/1234" or "IP_24_1234")

        Returns:
            Press release details or None
        """
        # Normalize reference format
        ref_clean = reference.replace('/', '_').replace('-', '_')

        url = f"{self.PRESS_CORNER}/detail/en/{ref_clean}"

        try:
            html = await self._fetch(url)
            soup = self._parse_html(html)

            title_elem = soup.select_one('h1, .page-title')
            date_elem = soup.select_one('.date, time, .press-release-date')
            body_elem = soup.select_one('.body-content, .press-release-body, article')
            image_elem = soup.select_one('img.featured-image, .press-image img')

            if not title_elem:
                return None

            # Extract body text
            body_text = None
            if body_elem:
                # Remove scripts and styles
                for tag in body_elem.select('script, style'):
                    tag.decompose()
                body_text = body_elem.get_text(separator='\n', strip=True)

            # Parse date
            date = None
            if date_elem:
                date = self._parse_date(date_elem.get_text(strip=True))

            return ScrapedNewsItem(
                source=DataSource.EUROPEAN_COMMISSION,
                source_url=url,
                source_id=reference,
                title=title_elem.get_text(strip=True),
                document_type=DocumentType.PRESS_RELEASE,
                published_at=date,
                body_text=body_text,
                summary=body_text[:500] + '...' if body_text and len(body_text) > 500 else body_text,
                image_url=self._make_absolute_url(image_elem['src']) if image_elem and image_elem.get('src') else None,
            )

        except Exception as e:
            logger.error(f"Failed to fetch press release {reference}: {e}")
            return None

    async def get_speeches(self, limit: int = 10) -> List[ScrapedNewsItem]:
        """
        Get recent Commissioner speeches.

        Args:
            limit: Maximum speeches to fetch

        Returns:
            List of speeches
        """
        return await self.get_press_releases(limit=limit, content_type=self.SPEECH)

    async def get_statements(self, limit: int = 10) -> List[ScrapedNewsItem]:
        """
        Get recent statements.

        Args:
            limit: Maximum statements to fetch

        Returns:
            List of statements
        """
        return await self.get_press_releases(limit=limit, content_type=self.STATEMENT)

    async def get_news_by_topic(self, topic: str, limit: int = 20) -> List[ScrapedNewsItem]:
        """
        Get news filtered by policy topic.

        Args:
            topic: Policy topic (e.g., "digital", "climate", "economy")
            limit: Maximum items

        Returns:
            List of news items
        """
        # Topic mappings to EC categories
        topic_mapping = {
            'digital': 'digital-economy-and-society',
            'climate': 'climate-action',
            'economy': 'economy-finance-and-euro',
            'trade': 'trade',
            'energy': 'energy',
            'migration': 'migration-and-asylum',
            'health': 'health',
            'agriculture': 'agriculture-and-rural-development',
        }

        topic_slug = topic_mapping.get(topic.lower(), topic.lower().replace(' ', '-'))

        url = f"https://commission.europa.eu/news/{topic_slug}_en"

        try:
            html = await self._fetch(url)
            soup = self._parse_html(html)

            news_items = []

            for item in soup.select('.news-item, .ecl-content-block, article'):
                news = self._parse_press_release_card(item)
                if news:
                    news.categories = [topic]
                    news_items.append(news)

            return news_items[:limit]

        except Exception as e:
            logger.warning(f"Failed to fetch news for topic {topic}: {e}")
            # Fallback to search
            results = await self.search(topic, limit=limit)
            return [
                ScrapedNewsItem(
                    source=DataSource.EUROPEAN_COMMISSION,
                    source_url=r.url,
                    source_id=r.id,
                    title=r.title,
                    document_type=r.document_type or DocumentType.NEWS,
                    published_at=r.date,
                    summary=r.snippet,
                    categories=[topic],
                )
                for r in results
            ]

    def _parse_press_release_card(self, elem) -> Optional[ScrapedNewsItem]:
        """Parse a press release card element"""
        title_elem = elem.select_one('h2 a, h3 a, .title a, a.ecl-link, a')
        if not title_elem:
            return None

        date_elem = elem.select_one('.date, time, .ecl-date-block')
        excerpt_elem = elem.select_one('.summary, .description, p')
        type_elem = elem.select_one('.type, .category')
        image_elem = elem.select_one('img')

        url = title_elem.get('href', '')
        if url and not url.startswith('http'):
            url = self._make_absolute_url(url)

        # Determine document type
        doc_type = DocumentType.PRESS_RELEASE
        if type_elem:
            type_text = type_elem.get_text(strip=True).upper()
            if 'SPEECH' in type_text:
                doc_type = DocumentType.SPEECH
            elif 'STATEMENT' in type_text:
                doc_type = DocumentType.PRESS_RELEASE

        # Parse date
        date = None
        if date_elem:
            date = self._parse_date(date_elem.get_text(strip=True))

        # Extract ID from URL
        source_id = url.split('/')[-1] if url else None

        return ScrapedNewsItem(
            source=DataSource.EUROPEAN_COMMISSION,
            source_url=url,
            source_id=source_id,
            title=title_elem.get_text(strip=True),
            document_type=doc_type,
            published_at=date,
            summary=excerpt_elem.get_text(strip=True)[:500] if excerpt_elem else None,
            image_url=self._make_absolute_url(image_elem['src']) if image_elem and image_elem.get('src') else None,
        )

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats from EC website"""
        if not date_str:
            return None

        # Clean up the string
        date_str = date_str.strip()

        # Common EC date formats
        formats = [
            '%d %B %Y',      # "15 January 2024"
            '%d/%m/%Y',      # "15/01/2024"
            '%Y-%m-%d',      # "2024-01-15"
            '%d %b %Y',      # "15 Jan 2024"
            '%B %d, %Y',     # "January 15, 2024"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # Try to extract date with regex
        date_match = re.search(r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})', date_str)
        if date_match:
            try:
                day, month, year = date_match.groups()
                return datetime(int(year), int(month), int(day))
            except ValueError:
                pass

        return None
