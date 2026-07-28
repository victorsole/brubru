"""
Brubru MCP Server -- EU Legislative Intelligence (stdio transport)

Exposes Brubru's knowledge base and database as MCP tools that any local AI
client (Claude Desktop, Cursor, Cline, Continue, VS Code) can call over stdio.

This is a THIN transport wrapper. All tool logic lives in the shared registry
services/mcp/tools.py, which the HTTP transport (api/mcp_http.py) also consumes
-- so the stdio and HTTP surfaces can never drift apart again. All corpus
counts are computed at runtime via services/mcp/stats.py, never hardcoded.

Primary tool:
    - ask_brubru: one free-text question -> guides + laws + procedure status

Advanced tools (rarely needed; ask_brubru covers most cases):
    - search_eu_legislation, search_knowledge_guides, get_procedure_status,
      get_calendar_events, search_eprs

Usage:
    Local:  python3.12 mcp_server.py
    Config: Add to .mcp.json as stdio server

Author: Victor Sole Ferioli, Beresol BV
"""

import json
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

from services.mcp import stats as _stats
from services.mcp.tools import (
    _handle_ask_brubru,
    _handle_get_calendar_events,
    _handle_get_procedure_status,
    _handle_search_eprs,
    _handle_search_eu_legislation,
    _handle_search_knowledge_guides,
)


def _instructions() -> str:
    try:
        coverage = _stats.format_summary()
    except Exception:  # noqa: BLE001
        coverage = "EU laws, knowledge guides, procedures, calendar events, EPRS publications"
    return (
        "Brubru is EU policy intelligence. For almost any question, call ask_brubru "
        "with the user's question -- it returns matching policy guides, the relevant "
        "EU laws (CELEX + EUR-Lex links), and live procedure status in one call. The "
        f"other tools are advanced and rarely needed. Live coverage: {coverage}."
    )


mcp = FastMCP("Brubru", instructions=_instructions())


def _dump(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


@mcp.tool()
def ask_brubru(question: str) -> str:
    """PRIMARY TOOL -- use this first for ANY question about the EU.

    One free-text question in, a combined answer out: the most relevant curated
    policy guides, the specific EU laws that match (CELEX + EUR-Lex links), and --
    if the question names a procedure reference like '2023/0131(COD)' -- its live
    legislative status. Prefer this over the narrower search tools.

    Examples:
        - "What is the status of the AI Act?"
        - "How does CBAM affect steel imports?"
        - "What EU regulations affect Spanish SMEs?"
    """
    return _dump(_handle_ask_brubru(question))


@mcp.tool()
def search_eu_legislation(query: str, limit: int = 10) -> str:
    """ADVANCED -- raw keyword search over the EU legislation database.

    Returns matching laws with CELEX numbers, titles and document types. Most
    callers should use ask_brubru instead (it already includes matching laws).

    Args:
        query: Search keywords (e.g. "artificial intelligence", "deforestation timber")
        limit: Maximum results (default 10, max 50)
    """
    return _dump(_handle_search_eu_legislation(query, limit))


@mcp.tool()
def search_knowledge_guides(query: str) -> str:
    """ADVANCED -- search only Brubru's curated EU policy knowledge guides.

    Each guide covers a policy domain with QUICK FACTS, CELEX numbers, key actors
    and current status. ask_brubru already returns matching guides plus laws.

    Args:
        query: Topic to search (e.g. "digital markets", "pharma legislation")
    """
    return _dump(_handle_search_knowledge_guides(query))


@mcp.tool()
def get_procedure_status(reference: str) -> str:
    """ADVANCED -- look up one EU legislative procedure by exact OEIL reference.

    ask_brubru resolves a procedure reference automatically when the question
    contains one; use this only for a direct lookup with no surrounding question.

    Args:
        reference: Procedure reference (e.g. "2023/0131(COD)", "2025/0076(NLE)")
    """
    return _dump(_handle_get_procedure_status(reference))


@mcp.tool()
def get_calendar_events(days_ahead: int = 14, institution: str = "") -> str:
    """Get upcoming EU institutional calendar events.

    Args:
        days_ahead: How many days ahead to look (default 14, max 90)
        institution: Filter by institution (EP, COUNCIL, EUROPEAN_COUNCIL, COMMISSION, or empty for all)
    """
    return _dump(_handle_get_calendar_events(days_ahead, institution))


@mcp.tool()
def search_eprs(query: str, limit: int = 10) -> str:
    """Search European Parliamentary Research Service (EPRS) publications.

    Covers briefings, at-a-glance notes, and studies from the EP Think Tank.

    Args:
        query: Search keywords (e.g. "defence funding", "cybercrime", "trade US")
        limit: Maximum results (default 10, max 30)
    """
    return _dump(_handle_search_eprs(query, limit))


if __name__ == "__main__":
    mcp.run(transport="stdio")
