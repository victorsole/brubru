"""
MCP Toolbox for Databases - Service Wrapper

Provides async access to the MCP Toolbox server for database-backed AI tools.
Gracefully degrades if the Toolbox server is unavailable.

Requires: toolbox-core>=0.5.0
Server: https://github.com/googleapis/genai-toolbox

Created: February 2026
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Singleton instance
_toolbox_service: Optional["ToolboxService"] = None


class ToolboxService:
    """
    Async wrapper around the MCP Toolbox for Databases.

    Connects to the Toolbox server (Go binary) on startup and loads
    SQL-based tools defined in tools.yaml. If the server is unavailable,
    all operations gracefully return None.

    Usage:
        service = get_toolbox_service()
        await service.connect()

        # Call a tool
        results = await service.call_tool("search_eu_laws", keyword="AI Act")

        # Check availability
        if service.available:
            ...

        await service.close()
    """

    def __init__(self, toolbox_url: str = "http://localhost:5000"):
        self.toolbox_url = toolbox_url
        self._client = None
        self._tools: Dict[str, Any] = {}
        self._available = False

    async def connect(self) -> bool:
        """
        Connect to Toolbox server and load tools.

        Non-fatal if unavailable - the backend continues without Toolbox.

        Returns:
            True if connection succeeded, False otherwise.
        """
        try:
            from toolbox_core import ToolboxClient

            self._client = ToolboxClient(self.toolbox_url)
            loaded_tools = await self._client.load_toolset("brubru_chatbot")
            self._tools = {tool.__name__: tool for tool in loaded_tools}
            self._available = True
            logger.info(
                f"[OK] MCP Toolbox connected at {self.toolbox_url} "
                f"({len(self._tools)} tools loaded)"
            )
            return True

        except Exception as e:
            logger.warning(
                f"[WARN] MCP Toolbox unavailable at {self.toolbox_url}: {e}. "
                f"Chat will use SQLAlchemy queries only."
            )
            self._available = False
            return False

    async def close(self):
        """Close the Toolbox client connection."""
        if self._client:
            try:
                await self._client.close()
                logger.info("[OK] MCP Toolbox connection closed")
            except Exception as e:
                logger.warning(f"[WARN] Error closing Toolbox connection: {e}")
            finally:
                self._client = None
                self._tools = {}
                self._available = False

    @property
    def available(self) -> bool:
        """Whether the Toolbox server is connected and tools are loaded."""
        return self._available

    @property
    def tool_names(self) -> List[str]:
        """List of available tool names."""
        return list(self._tools.keys())

    async def call_tool(self, name: str, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """
        Call a Toolbox tool by name with the given parameters.

        Args:
            name: Tool name (e.g. "search_eu_laws")
            **kwargs: Tool parameters (e.g. keyword="AI Act")

        Returns:
            List of result rows as dicts, or None if unavailable/failed.
        """
        if not self._available:
            return None

        if name not in self._tools:
            logger.warning(f"Toolbox tool '{name}' not found. Available: {self.tool_names}")
            return None

        try:
            result = await self._tools[name](**kwargs)
            logger.debug(f"Toolbox tool '{name}' returned {len(result) if result else 0} results")
            return result

        except Exception as e:
            logger.warning(f"Toolbox tool '{name}' failed: {e}")
            return None

    async def search_eu_laws(self, keyword: str) -> Optional[List[Dict[str, Any]]]:
        """Search EU legislation by keyword."""
        return await self.call_tool("search_eu_laws", keyword=keyword)

    async def get_law_by_celex(self, celex_number: str) -> Optional[List[Dict[str, Any]]]:
        """Get a specific EU law by CELEX number."""
        return await self.call_tool("get_law_by_celex", celex_number=celex_number)

    async def search_legislative_carriages(self, keyword: str) -> Optional[List[Dict[str, Any]]]:
        """Search legislative train carriages."""
        return await self.call_tool("search_legislative_carriages", keyword=keyword)

    async def get_recent_rss_entries(self, keyword: str = "%") -> Optional[List[Dict[str, Any]]]:
        """Get recent RSS news entries, optionally filtered by keyword."""
        return await self.call_tool("get_recent_rss_entries", keyword=keyword)

    async def search_committee_work(self, keyword: str) -> Optional[List[Dict[str, Any]]]:
        """Search EP committee work-in-progress items."""
        return await self.call_tool("search_committee_work", keyword=keyword)

    async def search_consultations(self, keyword: str) -> Optional[List[Dict[str, Any]]]:
        """Search EC public consultations."""
        return await self.call_tool("search_consultations", keyword=keyword)

    async def get_texts_adopted(self, keyword: str = "%") -> Optional[List[Dict[str, Any]]]:
        """Get recently adopted EP texts, optionally filtered by keyword."""
        return await self.call_tool("get_texts_adopted", keyword=keyword)

    async def get_user_tracked_files(self, user_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get legislative files tracked by a specific user."""
        return await self.call_tool("get_user_tracked_files", user_id=user_id)


def get_toolbox_service() -> ToolboxService:
    """Get the singleton ToolboxService instance."""
    global _toolbox_service
    if _toolbox_service is None:
        from core.config import settings
        toolbox_url = getattr(settings, 'TOOLBOX_URL', 'http://localhost:5000')
        _toolbox_service = ToolboxService(toolbox_url=toolbox_url)
    return _toolbox_service
