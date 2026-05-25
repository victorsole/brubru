"""
Brubru MCP tool registry (Phase C, 21 May 2026).

Single source of truth for the tools exposed to MCP clients (Claude Desktop,
Cursor, Cline, Continue, ChatGPT custom GPTs, etc.). Both the stdio MCP server
(backend/mcp_server.py) and the HTTP transport (backend/api/mcp_http.py)
consume this registry.

Each tool declares:
    - name           : MCP tool name (snake_case)
    - description    : What the tool does — read by the LLM to pick it
    - input_schema   : JSON Schema for inputs (per MCP spec)
    - scope          : Brubru API scope required (mirrors v1 REST scope catalogue)
    - cost_micro     : Per-call cost in micro-euros (defaults to MCP heavy)
    - handler        : Python callable that returns a JSON-serialisable dict

Tool calls go through:
    auth (api_key)  -> scope check  -> balance debit  -> handler  -> usage event

If handler raises, the billing middleware refunds the call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import text

# ---------------------------------------------------------------------------
# Costs (μEUR) — keep in sync with services/billing/pricing_table.json
# ---------------------------------------------------------------------------

COST_LIGHT_MCP = 5_000     # 0.005 EUR — most MCP tool calls
COST_HEAVY_MCP = 20_000    # 0.020 EUR — chat completion via MCP
COST_FREE_MCP = 0          # free


# ---------------------------------------------------------------------------
# Tool spec
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class McpTool:
    name: str
    description: str
    input_schema: Dict[str, Any]
    scope: Optional[str]   # None = no scope check (rare); otherwise read:laws etc.
    cost_micro: int
    handler: Callable[..., Dict[str, Any]]


# ---------------------------------------------------------------------------
# Lazy DB helper — same pattern as the stdio server
# ---------------------------------------------------------------------------

def _get_db():
    from core.database import SessionLocal
    return SessionLocal()


# ---------------------------------------------------------------------------
# Handlers (each returns a dict; the HTTP transport JSON-encodes it)
# ---------------------------------------------------------------------------

def _handle_ask_brubru(question: str) -> Dict[str, Any]:
    """Lightweight version: returns top 3 matching guides with QUICK FACTS.
    The full Claude pipeline is intentionally NOT invoked here — that's what
    a future `chat` MCP tool would do; currently this is a retrieval-only
    surface so its cost matches the read:knowledge price tier.
    """
    from knowledge_base.knowledge_loader import KnowledgeLoader

    loader = KnowledgeLoader()
    loader.load_all()
    guides = loader.search_guides(question)

    if not guides:
        return {
            "answer": "No knowledge guide matched this query. Try rephrasing or use search_eu_legislation for direct law search.",
            "guides_matched": 0,
            "top_guides": [],
        }

    results: List[Dict[str, Any]] = []
    for g in guides[:3]:
        guide_id = g["id"]
        content = loader.guides.get(guide_id, "")
        quick_facts = ""
        if "## QUICK FACTS" in content:
            start = content.index("## QUICK FACTS")
            end = content.index("\n## ", start + 15) if "\n## " in content[start + 15:] else start + 5000
            quick_facts = content[start:end].strip()[:4000]
        results.append({"guide_id": guide_id, "quick_facts": quick_facts})

    return {
        "question": question,
        "guides_matched": len(guides),
        "top_guides": results,
    }


def _handle_search_eu_legislation(query: str, limit: int = 10) -> Dict[str, Any]:
    """Full-text search over public.eu_laws.

    Important column gotcha:
        - `celex`            VARCHAR  -- the canonical CELEX like '32016R0679'
        - `celex_number`     INTEGER  -- just the numeric sub-part (679, 2847)
        We return `celex` so the caller gets the real reference, plus the cleaner
        `doc_type_normalized` when present (falls back to `doc_type`). Rows with
        no CELEX (older administrative decisions, working docs) are filtered out
        unless they have a meaningful title.
    """
    db = _get_db()
    limit = max(1, min(int(limit or 10), 50))
    try:
        rows = db.execute(
            text(
                """
                SELECT celex,
                       title,
                       COALESCE(doc_type_normalized, doc_type) AS doc_type,
                       ts_rank(search_vector, plainto_tsquery('english', :q)) AS rank
                FROM eu_laws
                WHERE search_vector @@ plainto_tsquery('english', :q)
                  AND celex IS NOT NULL
                ORDER BY rank DESC
                LIMIT :lim
                """
            ),
            {"q": query, "lim": limit},
        ).fetchall()

        laws = [
            {
                "celex": r[0],
                "title": (r[1] or "")[:300],
                "doc_type": r[2],
                "relevance": round(float(r[3]), 4),
                "url": f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{r[0]}" if r[0] else None,
            }
            for r in rows
        ]
        return {
            "query": query,
            "total_results": len(laws),
            "database_size_hint": 28_710,  # canonical 28,710 distinct laws (LEG_2025-11)
            "laws": laws,
        }
    finally:
        db.close()


def _handle_search_knowledge_guides(query: str) -> Dict[str, Any]:
    from knowledge_base.knowledge_loader import KnowledgeLoader

    loader = KnowledgeLoader()
    loader.load_all()
    guides = loader.search_guides(query)

    results: List[Dict[str, Any]] = []
    for g in guides[:5]:
        guide_id = g["id"]
        content = loader.guides.get(guide_id, "")
        results.append({"guide_id": guide_id, "preview": content[:500].strip()})

    return {
        "query": query,
        "total_guides": len(loader.guides),
        "matched": len(guides),
        "top_results": results,
    }


def _handle_get_procedure_status(reference: str) -> Dict[str, Any]:
    db = _get_db()
    try:
        row = db.execute(
            text(
                """
                SELECT title, current_status, oeil_procedure_ref,
                       lead_committee, text_type, policy_areas,
                       oeil_key_events, last_updated
                FROM legislative_carriages
                WHERE oeil_procedure_ref = :ref
                LIMIT 1
                """
            ),
            {"ref": reference},
        ).fetchone()

        if row is None:
            return {"error": f"Procedure {reference} not found", "reference": reference}

        return {
            "reference": reference,
            "title": row[0],
            "status": row[1],
            "oeil_ref": row[2],
            "lead_committee": row[3],
            "text_type": row[4],
            "policy_areas": row[5],
            "key_events": row[6],
            "last_updated": str(row[7]) if row[7] else None,
        }
    finally:
        db.close()


def _handle_get_calendar_events(days_ahead: int = 14, institution: str = "") -> Dict[str, Any]:
    db = _get_db()
    days_ahead = max(1, min(int(days_ahead or 14), 90))
    today = date.today()
    end_date = today + timedelta(days=days_ahead)
    try:
        sql = """
            SELECT title, description, institution, event_type,
                   start_date, end_date, ep_committee_code, policy_areas
            FROM eu_calendar_events
            WHERE start_date >= :start AND start_date <= :end
        """
        params: Dict[str, Any] = {"start": today, "end": end_date}
        if institution:
            sql += " AND institution = :inst"
            params["inst"] = institution
        sql += " ORDER BY start_date ASC LIMIT 30"

        rows = db.execute(text(sql), params).fetchall()
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
            for r in rows
        ]
        return {
            "period": f"{today} to {end_date}",
            "total_events": len(events),
            "events": events,
        }
    finally:
        db.close()


def _handle_search_eprs(query: str, limit: int = 10) -> Dict[str, Any]:
    db = _get_db()
    limit = max(1, min(int(limit or 10), 30))
    try:
        rows = db.execute(
            text(
                """
                SELECT title, publication_type, publication_date,
                       html_url, summary, policy_areas
                FROM eprs_publications
                WHERE title ILIKE :q OR summary ILIKE :q
                ORDER BY publication_date DESC
                LIMIT :lim
                """
            ),
            {"q": f"%{query}%", "lim": limit},
        ).fetchall()

        pubs = [
            {
                "title": r[0],
                "type": r[1],
                "date": str(r[2]) if r[2] else None,
                "url": r[3],
                "summary": (r[4] or "")[:400],
                "policy_areas": r[5],
            }
            for r in rows
        ]
        return {"query": query, "total_results": len(pubs), "publications": pubs}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TOOLS: List[McpTool] = [
    McpTool(
        name="ask_brubru",
        description=(
            "Ask any question about EU policy, legislation, or institutions. "
            "Returns the top 3 matching Brubru knowledge guides (curated by EU policy "
            "experts; covers 200+ topics including AI Act, GDPR, DSA, CSRD, MFF, CBAM). "
            "Use this when the user asks an open-ended policy question and you want "
            "structured background before drilling into specific laws."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "A natural-language EU policy question. E.g. 'What is the status of the AI Act?' or 'How does CBAM affect steel imports?'",
                },
            },
            "required": ["question"],
        },
        scope="read:knowledge",
        cost_micro=COST_LIGHT_MCP,
        handler=lambda question, **_: _handle_ask_brubru(question),
    ),
    McpTool(
        name="search_eu_legislation",
        description=(
            "Full-text search across Brubru's database of 28,710 distinct EU laws "
            "(28,513 OJ publications). Returns matching laws with CELEX number, title "
            "and document type, ranked by relevance. Use this when the user wants to "
            "find specific laws by keyword or topic."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords. E.g. 'artificial intelligence', 'deforestation timber', 'cyber resilience'"},
                "limit": {"type": "integer", "description": "Maximum results (default 10, capped at 50)", "default": 10, "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
        },
        scope="read:laws",
        cost_micro=COST_LIGHT_MCP,
        handler=lambda query, limit=10, **_: _handle_search_eu_legislation(query, limit),
    ),
    McpTool(
        name="search_knowledge_guides",
        description=(
            "Search Brubru's curated EU policy knowledge guides. Each guide covers a "
            "policy domain with QUICK FACTS, CELEX numbers, key actors, and current "
            "status. Updated daily. Use this when you want a structured policy briefing "
            "rather than raw law search."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Topic to search. E.g. 'digital markets', 'pharma legislation', 'cohesion policy'"},
            },
            "required": ["query"],
        },
        scope="read:knowledge",
        cost_micro=COST_LIGHT_MCP,
        handler=lambda query, **_: _handle_search_knowledge_guides(query),
    ),
    McpTool(
        name="get_procedure_status",
        description=(
            "Look up the live status of an EU legislative procedure by its OEIL "
            "reference. Returns title, current stage, lead committee, key events. "
            "Use when the user references a specific procedure number (e.g. "
            "'2023/0131(COD)', '2025/0076(NLE)')."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "OEIL procedure reference (e.g. '2023/0131(COD)')"},
            },
            "required": ["reference"],
        },
        scope="read:procedures",
        cost_micro=COST_LIGHT_MCP,
        handler=lambda reference, **_: _handle_get_procedure_status(reference),
    ),
    McpTool(
        name="get_calendar_events",
        description=(
            "Get upcoming EU institutional calendar events from the European Parliament, "
            "Council of the EU, European Council and Commission. Use when the user "
            "asks 'what's coming up' or 'when does X meet'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "description": "How many days ahead to look (default 14, max 90)", "default": 14, "minimum": 1, "maximum": 90},
                "institution": {"type": "string", "description": "Filter by institution: EP / COUNCIL / EUROPEAN_COUNCIL / COMMISSION. Leave empty for all."},
            },
            "required": [],
        },
        scope="read:calendar",
        cost_micro=COST_LIGHT_MCP,
        handler=lambda days_ahead=14, institution="", **_: _handle_get_calendar_events(days_ahead, institution),
    ),
    McpTool(
        name="search_eprs",
        description=(
            "Search European Parliamentary Research Service (EPRS) publications: "
            "briefings, at-a-glance notes and studies from the EP Think Tank. Use "
            "when the user wants in-depth background on a policy topic."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords. E.g. 'defence funding', 'cybercrime', 'EU-US trade'"},
                "limit": {"type": "integer", "description": "Maximum results (default 10, capped at 30)", "default": 10, "minimum": 1, "maximum": 30},
            },
            "required": ["query"],
        },
        scope="read:knowledge",
        cost_micro=COST_LIGHT_MCP,
        handler=lambda query, limit=10, **_: _handle_search_eprs(query, limit),
    ),
]


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def find_tool(name: str) -> Optional[McpTool]:
    for t in TOOLS:
        if t.name == name:
            return t
    return None


def list_tools_for_mcp() -> List[Dict[str, Any]]:
    """The MCP `tools/list` response shape: name + description + inputSchema."""
    return [
        {
            "name": t.name,
            "description": t.description,
            "inputSchema": t.input_schema,
        }
        for t in TOOLS
    ]


def invoke_tool(tool: McpTool, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Call the tool handler. Returns the dict result; the HTTP transport JSON-encodes it.

    Raises if required arguments are missing or the handler itself crashes.
    The billing middleware will refund a debit if the handler raises.
    """
    args = arguments or {}
    return tool.handler(**args)
