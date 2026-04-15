"""
Brubru MCP Server -- EU Legislative Intelligence

Exposes Brubru's knowledge base and database as MCP tools
that any AI assistant (Claude, GPT, etc.) can call.

Usage:
    Local:  python3.12 mcp_server.py
    Config: Add to .mcp.json as stdio server

Tools:
    - ask_brubru: Ask any EU policy question (uses full AI pipeline)
    - search_eu_legislation: Search 28,505 EU laws by keyword
    - search_knowledge_guides: Search 128 curated policy guides
    - get_procedure_status: Look up legislative procedure by reference
    - get_calendar_events: Get upcoming EU institutional events
    - search_eprs: Search EP Research Service publications

Author: Victor Sole Ferioli, Beresol BV
"""

import sys
import os
import json
from datetime import date, datetime, timedelta

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

# Initialise MCP server
mcp = FastMCP(
    "Brubru",
    instructions="EU legislative intelligence: 28,505 laws, 128 knowledge guides, 1,296 procedures, 417 calendar events. Use ask_brubru for general questions, search_eu_legislation for law search, search_knowledge_guides for policy guides.",
)


def _get_db():
    from core.database import SessionLocal
    return SessionLocal()


@mcp.tool()
def ask_brubru(question: str) -> str:
    """Ask any question about EU policy, legislation, or institutions.
    Uses Brubru's full knowledge base (128 guides, 4,616 triggers)
    and legislative database (28,505 laws, 1,296 procedures).
    Returns a comprehensive answer with document references.

    Examples:
        - "What EU regulations affect Spanish SMEs?"
        - "What is the status of the AI Act?"
        - "Explain the MFF 2028-2034 proposal"
        - "What are the CSRD reporting obligations?"
    """
    from knowledge_base.knowledge_loader import KnowledgeLoader

    loader = KnowledgeLoader()
    loader.load_all()

    # Search guides
    guides = loader.search_guides(question)

    if not guides:
        return json.dumps({
            "answer": "No knowledge guide matched this query. Try rephrasing or use search_eu_legislation for direct law search.",
            "guides_matched": 0,
        })

    # Return top 3 guides with QUICK FACTS
    results = []
    for g in guides[:3]:
        guide_id = g["id"]
        content = loader.guides.get(guide_id, "")
        # Extract QUICK FACTS section
        quick_facts = ""
        if "## QUICK FACTS" in content:
            start = content.index("## QUICK FACTS")
            end = content.index("\n## ", start + 15) if "\n## " in content[start + 15:] else start + 5000
            quick_facts = content[start:end].strip()[:4000]

        results.append({
            "guide_id": guide_id,
            "quick_facts": quick_facts,
        })

    return json.dumps({
        "question": question,
        "guides_matched": len(guides),
        "top_guides": results,
    }, ensure_ascii=False)


@mcp.tool()
def search_eu_legislation(query: str, limit: int = 10) -> str:
    """Search Brubru's database of 28,505 EU laws using full-text search.
    Returns matching laws with CELEX numbers, titles, and document types.

    Args:
        query: Search keywords (e.g. "artificial intelligence", "deforestation timber")
        limit: Maximum results (default 10, max 50)
    """
    from sqlalchemy import text

    db = _get_db()
    limit = min(limit, 50)

    try:
        results = db.execute(text("""
            SELECT celex_number, title, doc_type,
                   ts_rank(search_vector, plainto_tsquery('english', :q)) as rank
            FROM eu_laws
            WHERE search_vector @@ plainto_tsquery('english', :q)
            ORDER BY rank DESC
            LIMIT :lim
        """), {"q": query, "lim": limit}).fetchall()

        laws = [
            {
                "celex": r[0],
                "title": r[1][:200] if r[1] else None,
                "doc_type": r[2],
                "relevance": round(float(r[3]), 4),
            }
            for r in results
        ]

        return json.dumps({
            "query": query,
            "total_results": len(laws),
            "database_size": 28505,
            "laws": laws,
        }, ensure_ascii=False)

    finally:
        db.close()


@mcp.tool()
def search_knowledge_guides(query: str) -> str:
    """Search Brubru's 128 curated EU policy knowledge guides.
    Each guide covers a policy domain with QUICK FACTS, CELEX numbers,
    key actors, and current status. Updated daily.

    Args:
        query: Topic to search (e.g. "digital markets", "pharma legislation", "cohesion policy")
    """
    from knowledge_base.knowledge_loader import KnowledgeLoader

    loader = KnowledgeLoader()
    loader.load_all()
    guides = loader.search_guides(query)

    results = []
    for g in guides[:5]:
        guide_id = g["id"]
        content = loader.guides.get(guide_id, "")
        # First 500 chars as preview
        preview = content[:500].strip()
        results.append({
            "guide_id": guide_id,
            "preview": preview,
        })

    return json.dumps({
        "query": query,
        "total_guides": len(loader.guides),
        "matched": len(guides),
        "top_results": results,
    }, ensure_ascii=False)


@mcp.tool()
def get_procedure_status(reference: str) -> str:
    """Look up the status of an EU legislative procedure by its OEIL reference.

    Args:
        reference: Procedure reference (e.g. "2023/0131(COD)", "2025/0076(NLE)")
    """
    from sqlalchemy import text

    db = _get_db()
    try:
        result = db.execute(text("""
            SELECT title, current_status, oeil_procedure_ref,
                   lead_committee, text_type, policy_areas,
                   oeil_key_events, last_updated
            FROM legislative_carriages
            WHERE oeil_procedure_ref = :ref
            LIMIT 1
        """), {"ref": reference}).fetchone()

        if not result:
            return json.dumps({"error": f"Procedure {reference} not found in database (1,296 procedures tracked)"})

        return json.dumps({
            "reference": reference,
            "title": result[0],
            "status": result[1],
            "oeil_ref": result[2],
            "lead_committee": result[3],
            "text_type": result[4],
            "policy_areas": result[5],
            "key_events": result[6],
            "last_updated": str(result[7]) if result[7] else None,
        }, ensure_ascii=False, default=str)

    finally:
        db.close()


@mcp.tool()
def get_calendar_events(days_ahead: int = 14, institution: str = "") -> str:
    """Get upcoming EU institutional calendar events.

    Args:
        days_ahead: How many days ahead to look (default 14, max 90)
        institution: Filter by institution (EP, COUNCIL, EUROPEAN_COUNCIL, COMMISSION, or empty for all)
    """
    from sqlalchemy import text

    db = _get_db()
    days_ahead = min(days_ahead, 90)
    today = date.today()
    end_date = today + timedelta(days=days_ahead)

    try:
        query = """
            SELECT title, description, institution, event_type,
                   start_date, end_date, ep_committee_code, policy_areas
            FROM eu_calendar_events
            WHERE start_date >= :start AND start_date <= :end
        """
        params = {"start": today, "end": end_date}

        if institution:
            query += " AND institution = :inst"
            params["inst"] = institution

        query += " ORDER BY start_date ASC LIMIT 30"

        results = db.execute(text(query), params).fetchall()

        events = [
            {
                "title": r[0],
                "description": (r[1] or "")[:300],
                "institution": r[2],
                "event_type": r[3],
                "start_date": str(r[4]),
                "end_date": str(r[5]) if r[5] else None,
                "committee": r[6],
                "policy_areas": r[7],
            }
            for r in results
        ]

        return json.dumps({
            "period": f"{today} to {end_date}",
            "total_events": len(events),
            "events": events,
        }, ensure_ascii=False, default=str)

    finally:
        db.close()


@mcp.tool()
def search_eprs(query: str, limit: int = 10) -> str:
    """Search European Parliamentary Research Service (EPRS) publications.
    Covers briefings, at-a-glance notes, and studies from the EP Think Tank.

    Args:
        query: Search keywords (e.g. "defence funding", "cybercrime", "trade US")
        limit: Maximum results (default 10)
    """
    from sqlalchemy import text

    db = _get_db()
    limit = min(limit, 30)

    try:
        results = db.execute(text("""
            SELECT title, publication_type, publication_date,
                   html_url, summary, policy_areas
            FROM eprs_publications
            WHERE title ILIKE :q OR summary ILIKE :q
            ORDER BY publication_date DESC
            LIMIT :lim
        """), {"q": f"%{query}%", "lim": limit}).fetchall()

        pubs = [
            {
                "title": r[0],
                "type": r[1],
                "date": str(r[2]) if r[2] else None,
                "url": r[3],
                "summary": (r[4] or "")[:400],
                "policy_areas": r[5],
            }
            for r in results
        ]

        return json.dumps({
            "query": query,
            "total_results": len(pubs),
            "publications": pubs,
        }, ensure_ascii=False, default=str)

    finally:
        db.close()


if __name__ == "__main__":
    mcp.run(transport="stdio")
