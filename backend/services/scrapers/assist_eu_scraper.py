"""
AssistEU Scraper

DEPRECATED (January 2025):
- AssistEU service has limited relevance for Brubru's use cases
- No active maintenance or development planned
- Consider removing in future cleanup

If you need this functionality, implement it properly or find alternative source.
"""

import warnings
from .base_scraper import BaseScraper

warnings.warn(
    "AssistEUScraper is deprecated and may be removed in a future version.",
    DeprecationWarning,
    stacklevel=2
)


class AssistEUScraper(BaseScraper):
    """
    DEPRECATED: AssistEU Scraper

    This scraper is a stub and not actively maintained.
    Consider using EuropeanCommissionScraper or other active scrapers instead.
    """

    def __init__(self, **kwargs):
        super().__init__(
            base_url="https://assist.eu/",
            name="AssistEU",
            **kwargs
        )
        warnings.warn(
            "AssistEUScraper is deprecated. Consider using EuropeanCommissionScraper instead.",
            DeprecationWarning,
            stacklevel=2
        )

    async def search(self, query: str, **kwargs):
        """DEPRECATED: Returns empty list"""
        return []

    async def get_document(self, document_id: str):
        """DEPRECATED: Returns empty dict"""
        return {}

    async def get_latest_updates(self, limit: int = 10):
        """DEPRECATED: Returns empty list"""
        return []
