"""
Interinstitutional Style Guide Scraper

DEPRECATED (January 2025):
- Style guide content rarely changes
- Static reference data can be stored locally instead
- No active maintenance or development planned

If you need style guide data, consider fetching it once and storing locally
rather than using this scraper repeatedly.
"""

import warnings
from .base_scraper import BaseScraper

warnings.warn(
    "StyleGuideScraper is deprecated and may be removed in a future version.",
    DeprecationWarning,
    stacklevel=2
)


class StyleGuideScraper(BaseScraper):
    """
    DEPRECATED: Interinstitutional Style Guide Scraper

    This scraper is a stub and not actively maintained.
    Style guide data is mostly static and can be stored locally.
    """

    def __init__(self, **kwargs):
        super().__init__(
            base_url="https://style-guide.europa.eu/en/",
            name="StyleGuide",
            **kwargs
        )
        warnings.warn(
            "StyleGuideScraper is deprecated. Style guide data is mostly static; consider storing locally.",
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
