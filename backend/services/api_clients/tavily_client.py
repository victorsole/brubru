"""
Tavily Search API Client

Real-time web search optimized for AI agents.
Provides current news, statements, and web content to complement
Brubru's EU institutional databases.

Use cases:
- Breaking EU policy news
- Recent statements by MEPs, commissioners
- Current events not yet in EUR-Lex/OEIL
- Stakeholder research (companies, NGOs, think tanks)
"""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from .base_api_client import BaseAPIClient, AuthType, ResponseFormat

logger = logging.getLogger(__name__)


@dataclass
class TavilySearchResult:
    """Single search result from Tavily"""
    title: str
    url: str
    content: str  # Excerpt/snippet
    score: float  # Relevance score
    published_date: Optional[str] = None
    raw_content: Optional[str] = None  # Full content if available


@dataclass
class TavilySearchResponse:
    """Complete Tavily search response"""
    query: str
    results: List[TavilySearchResult]
    answer: Optional[str]  # AI-generated answer if requested
    response_time: float
    images: List[str]  # Image URLs if any


class TavilyClient(BaseAPIClient):
    """
    Client for Tavily Search API.

    Provides real-time web search optimized for AI/LLM consumption.
    Results include citations and are formatted for RAG workflows.

    Docs: https://docs.tavily.com/
    """

    def __init__(
        self,
        api_key: str,
        max_results: int = 5,
        search_depth: str = "basic",  # "basic" or "advanced"
        include_answer: bool = True,
        include_raw_content: bool = False,
        timeout: int = 30
    ):
        """
        Initialize Tavily client.

        Args:
            api_key: Tavily API key
            max_results: Maximum results per search (1-10)
            search_depth: "basic" (faster) or "advanced" (more thorough)
            include_answer: Include AI-generated answer summary
            include_raw_content: Include full page content (uses more tokens)
            timeout: Request timeout in seconds
        """
        super().__init__(
            base_url="https://api.tavily.com",
            auth_type=AuthType.NONE,  # API key sent in body
            api_key=api_key,
            rate_limit_calls=100,  # 100 calls per minute
            rate_limit_period=60,
            timeout=timeout
        )

        self.max_results = min(max_results, 10)
        self.search_depth = search_depth
        self.include_answer = include_answer
        self.include_raw_content = include_raw_content

        logger.info(
            f"Initialized TavilyClient (depth={search_depth}, "
            f"max_results={max_results})"
        )

    async def search(
        self,
        query: str,
        search_depth: Optional[str] = None,
        max_results: Optional[int] = None,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        topic: str = "general"  # "general" or "news"
    ) -> TavilySearchResponse:
        """
        Perform web search.

        Args:
            query: Search query
            search_depth: Override default search depth
            max_results: Override default max results
            include_domains: Only include results from these domains
            exclude_domains: Exclude results from these domains
            topic: "general" for broad search, "news" for recent news

        Returns:
            TavilySearchResponse with results and optional AI answer

        Example:
            >>> results = await client.search("AI Act implementation timeline")
            >>> for r in results.results:
            ...     print(f"{r.title}: {r.url}")
        """
        start_time = datetime.now()

        # Build request body
        body = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": search_depth or self.search_depth,
            "max_results": max_results or self.max_results,
            "include_answer": self.include_answer,
            "include_raw_content": self.include_raw_content,
            "topic": topic
        }

        if include_domains:
            body["include_domains"] = include_domains
        if exclude_domains:
            body["exclude_domains"] = exclude_domains

        logger.debug(f"Tavily search: {query}")

        try:
            response = await self.post(
                "/search",
                json=body,
                response_format=ResponseFormat.JSON
            )

            data = response.json()

            # Parse results
            results = []
            for item in data.get("results", []):
                results.append(TavilySearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content", ""),
                    score=item.get("score", 0.0),
                    published_date=item.get("published_date"),
                    raw_content=item.get("raw_content")
                ))

            response_time = (datetime.now() - start_time).total_seconds()

            search_response = TavilySearchResponse(
                query=query,
                results=results,
                answer=data.get("answer"),
                response_time=response_time,
                images=data.get("images", [])
            )

            logger.info(
                f"Tavily search completed: {len(results)} results "
                f"in {response_time:.2f}s"
            )

            return search_response

        except Exception as e:
            logger.error(f"Tavily search failed: {str(e)}")
            raise

    async def search_eu_news(
        self,
        query: str,
        max_results: Optional[int] = None
    ) -> TavilySearchResponse:
        """
        Search for EU-related news.

        Optimized for EU policy news by:
        - Using "news" topic for recent content
        - Prioritizing EU institutional and policy news sources

        Args:
            query: Search query (EU policy related)
            max_results: Override default max results

        Returns:
            TavilySearchResponse focused on news
        """
        # Prioritize quality EU news sources
        include_domains = [
            "politico.eu",
            "euractiv.com",
            "europarl.europa.eu",
            "consilium.europa.eu",
            "ec.europa.eu",
            "reuters.com",
            "ft.com",
            "euronews.com",
            "euobserver.com"
        ]

        return await self.search(
            query=query,
            topic="news",
            max_results=max_results,
            include_domains=include_domains
        )

    async def search_stakeholder(
        self,
        entity_name: str,
        context: str = "EU policy",
        max_results: Optional[int] = None
    ) -> TavilySearchResponse:
        """
        Search for information about a stakeholder.

        Args:
            entity_name: Name of person, organisation, or company
            context: Context for the search (default: EU policy)
            max_results: Override default max results

        Returns:
            TavilySearchResponse with stakeholder information

        Example:
            >>> results = await client.search_stakeholder("Thierry Breton")
            >>> print(results.answer)  # AI summary of who they are
        """
        query = f"{entity_name} {context}"

        return await self.search(
            query=query,
            search_depth="advanced",  # More thorough for stakeholder research
            max_results=max_results
        )

    async def extract_content(
        self,
        urls: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Extract structured content from URLs.

        Uses Tavily Extract API to pull clean content from web pages.

        Args:
            urls: List of URLs to extract content from (max 20)

        Returns:
            List of extracted content with URL and text
        """
        if len(urls) > 20:
            urls = urls[:20]
            logger.warning("Truncated URLs to 20 (Tavily limit)")

        body = {
            "api_key": self.api_key,
            "urls": urls
        }

        try:
            response = await self.post(
                "/extract",
                json=body,
                response_format=ResponseFormat.JSON
            )

            data = response.json()

            results = []
            for item in data.get("results", []):
                results.append({
                    "url": item.get("url", ""),
                    "raw_content": item.get("raw_content", ""),
                    "failed": False
                })

            # Handle failed extractions
            for failed_url in data.get("failed_results", []):
                results.append({
                    "url": failed_url,
                    "raw_content": "",
                    "failed": True
                })

            logger.info(f"Extracted content from {len(results)} URLs")
            return results

        except Exception as e:
            logger.error(f"Tavily extract failed: {str(e)}")
            raise

    async def health_check(self) -> bool:
        """Check if Tavily API is accessible"""
        try:
            # Simple search to verify API key works
            await self.search("test", max_results=1)
            return True
        except Exception as e:
            logger.error(f"Tavily health check failed: {str(e)}")
            return False


# Global singleton
_tavily_client: Optional[TavilyClient] = None


def get_tavily_client() -> Optional[TavilyClient]:
    """
    Get global Tavily client instance.

    Returns:
        TavilyClient if configured, None otherwise
    """
    global _tavily_client

    if _tavily_client is None:
        from ...core.config import settings

        if settings.TAVILY_API_KEY and settings.TAVILY_ENABLED:
            _tavily_client = TavilyClient(
                api_key=settings.TAVILY_API_KEY,
                max_results=settings.TAVILY_MAX_RESULTS,
                search_depth=settings.TAVILY_SEARCH_DEPTH
            )
        else:
            logger.info("Tavily not configured or disabled")
            return None

    return _tavily_client
