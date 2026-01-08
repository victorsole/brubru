"""
EUR-Lex Document Fetcher

Fetches and parses EU legal documents from EUR-Lex.
Strategy:
1. Check local database (28k+ laws from LEG_2025-11 archive)
2. Fall back to EUR-Lex web API if not found locally

Usage:
    from backend.services.parsers.eurlex_fetcher import EurlexFetcher

    fetcher = EurlexFetcher(db_session)

    # Fetch by CELEX number
    result = await fetcher.get_law("32024R1689")

    # Fetch by EUR-Lex URL
    result = await fetcher.get_law_from_url("https://eur-lex.europa.eu/...")
"""

import re
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import httpx
from sqlalchemy.orm import Session

from .formex_parser import FormexParser, ParsedLaw
from .eurlex_parser import EurlexParser, ParsedEurlexDocument

logger = logging.getLogger(__name__)


@dataclass
class LawResult:
    """Unified result from either local archive or web fetch."""
    celex: str
    title: str
    short_title: str = ""
    doc_type: str = ""
    date: Optional[datetime] = None
    oj_reference: str = ""
    policy_area: str = ""

    # Content
    articles: list = field(default_factory=list)
    recitals: list = field(default_factory=list)
    annexes: list = field(default_factory=list)

    # Legal relationships
    legal_basis: list = field(default_factory=list)
    citations: list = field(default_factory=list)

    # Source info
    source: str = "unknown"  # "local" or "web"
    xml_path: str = ""
    url: str = ""

    # Extra metadata
    extra_metadata: dict = field(default_factory=dict)


class EurlexFetcher:
    """
    Fetches EU legal documents from local archive or EUR-Lex web.

    The fetcher prioritizes local documents from the LEG_2025-11 archive
    (28k+ documents) for speed and reliability, falling back to web
    fetch for documents not in the archive.
    """

    # EUR-Lex URL patterns
    EURLEX_HTML_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:{celex}"
    EURLEX_XML_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/XML/?uri=CELEX:{celex}"

    # CELEX pattern: e.g., 32024R1689 (year-type-number)
    CELEX_PATTERN = re.compile(r'^[0-9]{5}[A-Z][0-9]{4}$')

    def __init__(self, db: Optional[Session] = None, archive_path: Optional[str] = None):
        """
        Initialize fetcher.

        Args:
            db: SQLAlchemy database session (for local lookups)
            archive_path: Path to LEG_2025-11 archive (for XML parsing)
        """
        self.db = db
        self.archive_path = Path(archive_path) if archive_path else None
        self.formex_parser = FormexParser()
        self.eurlex_parser = EurlexParser()

        # HTTP client with sensible defaults
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy-initialize async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Brubru/1.0 (EU Policy Assistant; +https://brubru.eu)",
                    "Accept": "text/html,application/xhtml+xml,application/xml",
                    "Accept-Language": "en",
                }
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def normalize_celex(self, celex_or_url: str) -> Optional[str]:
        """
        Extract and normalize CELEX number from input.

        Args:
            celex_or_url: Either a CELEX number or EUR-Lex URL

        Returns:
            Normalized CELEX number or None if invalid
        """
        # Direct CELEX
        if self.CELEX_PATTERN.match(celex_or_url):
            return celex_or_url

        # Extract from URL
        celex_match = re.search(r'CELEX[=:](\d{5}[A-Z]\d{4})', celex_or_url)
        if celex_match:
            return celex_match.group(1)

        # Try finding any CELEX pattern
        celex_match = re.search(r'\b(\d{5}[A-Z]\d{4})\b', celex_or_url)
        if celex_match:
            return celex_match.group(1)

        return None

    async def get_law(self, celex_or_url: str, prefer_web: bool = False) -> Optional[LawResult]:
        """
        Fetch a law by CELEX number or URL.

        Args:
            celex_or_url: CELEX number (e.g., "32024R1689") or EUR-Lex URL
            prefer_web: If True, skip local lookup and fetch from web

        Returns:
            LawResult with parsed content, or None if not found
        """
        celex = self.normalize_celex(celex_or_url)
        if not celex:
            logger.warning(f"Could not extract CELEX from: {celex_or_url}")
            return None

        # Try local first (unless prefer_web)
        if not prefer_web and self.db:
            local_result = self._get_from_local(celex)
            if local_result:
                logger.info(f"Found {celex} in local archive")
                return local_result

        # Fetch from web
        web_result = await self._get_from_web(celex)
        if web_result:
            logger.info(f"Fetched {celex} from EUR-Lex web")
            return web_result

        logger.warning(f"Could not find law: {celex}")
        return None

    def _get_from_local(self, celex: str) -> Optional[LawResult]:
        """
        Get law from local database/archive.

        Args:
            celex: CELEX number

        Returns:
            LawResult if found locally, None otherwise
        """
        if not self.db:
            return None

        try:
            # Import here to avoid circular imports
            from backend.models.eu_law import EULaw

            # Query database
            law = self.db.query(EULaw).filter(EULaw.celex == celex).first()
            if not law:
                return None

            # Parse XML if available
            articles = []
            recitals = []
            annexes = []

            if law.xml_path and Path(law.xml_path).exists():
                try:
                    parsed = self.formex_parser.parse_file(law.xml_path)
                    articles = [
                        {"number": a.number, "title": a.title, "paragraphs": [p.__dict__ for p in a.paragraphs]}
                        for a in parsed.articles
                    ]
                    recitals = [{"number": r.number, "text": r.text} for r in parsed.recitals]
                    annexes = [{"id": a.id, "title": a.title} for a in parsed.annexes]
                except Exception as e:
                    logger.warning(f"Could not parse XML for {celex}: {e}")

            return LawResult(
                celex=law.celex,
                title=law.title,
                short_title=law.extra_metadata.get("short_title", "") if law.extra_metadata else "",
                doc_type=law.doc_type or "",
                date=law.date,
                oj_reference=law.oj_reference or "",
                policy_area=law.policy_area or "",
                articles=articles,
                recitals=recitals,
                annexes=annexes,
                legal_basis=law.legal_basis or [],
                citations=law.citations or [],
                source="local",
                xml_path=law.xml_path or "",
                extra_metadata=law.extra_metadata or {}
            )

        except Exception as e:
            logger.error(f"Error fetching {celex} from local: {e}")
            return None

    async def _get_from_web(self, celex: str) -> Optional[LawResult]:
        """
        Fetch law from EUR-Lex web.

        Args:
            celex: CELEX number

        Returns:
            LawResult if successfully fetched, None otherwise
        """
        url = self.EURLEX_HTML_URL.format(celex=celex)

        try:
            response = await self.client.get(url)

            if response.status_code != 200:
                logger.warning(f"EUR-Lex returned {response.status_code} for {celex}")
                return None

            html = response.text

            # Parse HTML
            parsed = self.eurlex_parser.parse_html(html)

            # Convert to LawResult
            articles = [
                {
                    "number": a.number,
                    "title": a.title,
                    "html": a.html,
                    "division": a.division.__dict__ if a.division else None
                }
                for a in parsed.articles
            ]

            recitals = [
                {"number": r.number, "text": r.text, "html": r.html}
                for r in parsed.recitals
            ]

            annexes = [
                {"id": a.id, "title": a.title, "html": a.html}
                for a in parsed.annexes
            ]

            # Extract doc type from title
            doc_type = ""
            title = parsed.title
            if "Regulation" in title:
                doc_type = "Regulation"
            elif "Directive" in title:
                doc_type = "Directive"
            elif "Decision" in title:
                doc_type = "Decision"
            elif "Recommendation" in title:
                doc_type = "Recommendation"

            return LawResult(
                celex=celex,
                title=parsed.title,
                short_title=parsed.short_title,
                doc_type=doc_type,
                articles=articles,
                recitals=recitals,
                annexes=annexes,
                source="web",
                url=url,
                extra_metadata={
                    "article_count": len(articles),
                    "recital_count": len(recitals),
                    "annex_count": len(annexes),
                }
            )

        except httpx.TimeoutException:
            logger.error(f"Timeout fetching {celex} from EUR-Lex")
            return None
        except Exception as e:
            logger.error(f"Error fetching {celex} from web: {e}")
            return None

    async def search_laws(
        self,
        query: str,
        policy_area: Optional[str] = None,
        doc_type: Optional[str] = None,
        limit: int = 20
    ) -> list[dict]:
        """
        Search laws in local database.

        Args:
            query: Search query (matches title)
            policy_area: Filter by policy area
            doc_type: Filter by document type (Regulation, Directive, etc.)
            limit: Maximum results

        Returns:
            List of matching laws (summary info only)
        """
        if not self.db:
            logger.warning("No database session - cannot search locally")
            return []

        try:
            from backend.models.eu_law import EULaw

            # Build query
            db_query = self.db.query(EULaw)

            if query:
                db_query = db_query.filter(EULaw.title.ilike(f"%{query}%"))

            if policy_area:
                db_query = db_query.filter(EULaw.policy_area == policy_area)

            if doc_type:
                db_query = db_query.filter(EULaw.doc_type.ilike(f"%{doc_type}%"))

            # Order by date (newest first) and limit
            results = db_query.order_by(EULaw.date.desc()).limit(limit).all()

            return [
                {
                    "celex": law.celex,
                    "title": law.title,
                    "doc_type": law.doc_type,
                    "date": law.date.isoformat() if law.date else None,
                    "policy_area": law.policy_area,
                }
                for law in results
            ]

        except Exception as e:
            logger.error(f"Error searching laws: {e}")
            return []

    def get_law_sync(self, celex_or_url: str) -> Optional[LawResult]:
        """
        Synchronous version of get_law (local only).

        For use in sync contexts. Only checks local database.

        Args:
            celex_or_url: CELEX number or URL

        Returns:
            LawResult if found locally, None otherwise
        """
        celex = self.normalize_celex(celex_or_url)
        if not celex:
            return None

        return self._get_from_local(celex)


# Convenience function for quick fetches
async def fetch_law(celex: str, db: Optional[Session] = None) -> Optional[LawResult]:
    """
    Quick fetch of a single law.

    Args:
        celex: CELEX number
        db: Optional database session for local lookup

    Returns:
        LawResult or None
    """
    fetcher = EurlexFetcher(db=db)
    try:
        return await fetcher.get_law(celex)
    finally:
        await fetcher.close()
