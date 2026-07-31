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
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import text

# OEIL procedure reference, e.g. "2023/0131(COD)" or "2025/0076(NLE)".
_PROC_REF = re.compile(r"\b(\d{4}/\d{4}\s*\([A-Z]{2,4}\))")

# Stop-words dropped when relaxing a conversational query to an OR search.
_STOP = {
    "what", "when", "where", "which", "does", "affect", "affects", "about", "with",
    "from", "into", "that", "this", "have", "will", "would", "should", "there",
    "status", "under", "tell", "explain", "show", "find", "give", "much", "many",
    "your", "they", "them", "than", "then", "here", "over", "some", "such",
    "opportunit", "opportunities", "opportunity", "funding", "grants", "grant",
    "call", "calls", "scheme", "schemes", "available", "open",
}

# When ask_brubru should ALSO pull live EU funding calls (not just guide facts).
_FUNDING_INTENT = re.compile(
    r"\b(funding|grants?|subsid\w+|calls?\s+for\s+proposals?|tenders?|"
    r"horizon|eafrd|eagf|eco-?schemes?|cohesion\s+fund|life\s+programme|"
    r"financing|opportunit\w+)\b",
    re.IGNORECASE,
)

# Light domain-synonym expansion so a broad topic hits the calls' actual vocabulary
# (calls are titled by specific topic, rarely by the umbrella word "agriculture").
_FUNDING_SYNONYMS = {
    "agriculture": ["agri", "farm", "rural", "food"],
    "agricultural": ["agri", "farm", "rural"],
    "farming": ["agri", "farm", "rural"],
    "farmers": ["agri", "farm", "rural"],
    "health": ["health", "medical", "pharma"],
    "climate": ["climate", "green", "emission"],
    "digital": ["digital", "data", "cyber"],
    "energy": ["energy", "renewable", "hydrogen"],
    "defence": ["defence", "security", "military"],
}


def _related_laws(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Laws for the ask_brubru front door. Precise first, then relaxed.

    Tries plainto_tsquery (all terms, high precision). If that finds nothing --
    common for conversational phrasing like 'how does CBAM affect steel?' -- it
    falls back to an OR of the significant words so the answer still carries real
    CELEX references. Kept out of the advanced search_eu_legislation tool, whose
    AND semantics direct callers rely on.
    """
    laws = _handle_search_eu_legislation(query, limit=limit).get("laws", [])
    if laws:
        return laws

    terms = [
        w for w in re.findall(r"[A-Za-z]{4,}", query)
        if w.lower() not in _STOP
    ]
    if not terms:
        return []

    db = _get_db()
    try:
        or_query = " | ".join(terms[:8])
        rows = db.execute(
            text(
                """
                SELECT celex,
                       title,
                       COALESCE(doc_type_normalized, doc_type) AS doc_type,
                       ts_rank(search_vector, to_tsquery('english', :q)) AS rank
                FROM eu_laws
                WHERE search_vector @@ to_tsquery('english', :q)
                  AND celex IS NOT NULL
                ORDER BY rank DESC
                LIMIT :lim
                """
            ),
            {"q": or_query, "lim": limit},
        ).fetchall()
        return [
            {
                "celex": r[0],
                "title": (r[1] or "")[:300],
                "doc_type": r[2],
                "relevance": round(float(r[3]), 4),
                "url": f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{r[0]}" if r[0] else None,
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001
        return []
    finally:
        db.close()

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
# Live EU funding calls (funding_opportunities, synced daily from the F&T Portal)
# ---------------------------------------------------------------------------

def _funding_rows(where_extra: str, params: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    db = _get_db()
    params = {**params, "lim": limit}
    try:
        rows = db.execute(
            text(
                f"""
                SELECT topic_id, programme, title, short_summary, status,
                       to_char(deadline, 'YYYY-MM-DD') AS deadline,
                       indicative_budget, budget_currency, source_url
                FROM funding_opportunities
                WHERE is_test = false AND lower(status) IN ('open', 'forthcoming')
                {where_extra}
                ORDER BY (lower(status) = 'open') DESC, deadline ASC NULLS LAST
                LIMIT :lim
                """
            ),
            params,
        ).fetchall()
        return [
            {
                "topic_id": r[0],
                "programme": r[1],
                "title": (r[2] or "")[:160],
                "summary": (r[3] or "")[:280],
                "status": r[4],
                "deadline": r[5],
                "budget": (f"{float(r[6]):,.0f} {r[7] or 'EUR'}" if r[6] is not None else None),
                "url": r[8],
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001
        return []
    finally:
        db.close()


def _related_funding(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    """Live open/forthcoming EU funding calls matching a free-text query.

    ask_brubru maps policy 'architecture'; without this it never surfaces the
    actual open calls (with deadlines + apply URLs) that Brubru syncs daily. A
    broad topic is expanded via _FUNDING_SYNONYMS because calls are titled by
    specific topic, not the umbrella word. Falls back to the soonest open calls.
    """
    words = [w.lower() for w in re.findall(r"[A-Za-z]{4,}", query) if w.lower() not in _STOP]
    terms: List[str] = []
    for w in words:
        terms.append(w)
        terms.extend(_FUNDING_SYNONYMS.get(w, []))
    seen: set = set()
    terms = [t for t in terms if not (t in seen or seen.add(t))]

    if terms:
        ors, params = [], {}
        for i, t in enumerate(terms[:8]):
            k = f"t{i}"
            params[k] = f"%{t}%"
            ors.append(
                f"(title ILIKE :{k} OR short_summary ILIKE :{k} OR programme ILIKE :{k} "
                f"OR array_to_string(keywords, ' ') ILIKE :{k})"
            )
        rows = _funding_rows("AND (" + " OR ".join(ors) + ")", params, limit)
        if rows:
            return rows
    # No term match (or no terms) -> the soonest open/forthcoming calls.
    return _funding_rows("", {}, limit)


def _handle_search_funding(query: str = "", limit: int = 15) -> Dict[str, Any]:
    """Search live open + forthcoming EU funding calls."""
    limit = max(1, min(int(limit or 15), 40))
    items = _related_funding(query or "", limit=limit)
    return {"query": query, "total_results": len(items), "opportunities": items}


# ---------------------------------------------------------------------------
# Domain tools — direct, safe DB reads over specific EU datasets. One shared
# helper so each domain is a few lines. AND across query terms, OR across the
# match columns; array columns are matched via ::text.
# ---------------------------------------------------------------------------

def _simple_search(select_cols: str, table: str, match_cols: List[str],
                   query: str, limit: int, order_by: str = "",
                   extra_where: str = "") -> List[Dict[str, Any]]:
    terms = [w for w in re.findall(r"[A-Za-z0-9]{3,}", query or "") if w.lower() not in _STOP]
    params: Dict[str, Any] = {"lim": max(1, min(int(limit or 15), 40))}
    where = ["1=1"]
    if extra_where:
        where.append(extra_where)
    if terms:
        for i, t in enumerate(terms[:6]):
            k = f"t{i}"
            params[k] = f"%{t}%"
            where.append("(" + " OR ".join(f"{c} ILIKE :{k}" for c in match_cols) + ")")
    sql = f"SELECT {select_cols} FROM {table} WHERE " + " AND ".join(where)
    if order_by:
        sql += f" ORDER BY {order_by}"
    sql += " LIMIT :lim"
    db = _get_db()
    try:
        return [dict(r) for r in db.execute(text(sql), params).mappings().all()]
    except Exception:  # noqa: BLE001
        return []
    finally:
        db.close()


def _handle_search_sanctions(query: str = "", limit: int = 15) -> Dict[str, Any]:
    items = _simple_search(
        "eu_ref_num, full_name, subject_type, programme, function, aliases, legal_basis_title, legal_basis_url",
        "eu_sanctions",
        ["full_name", "aliases::text", "programme", "function", "legal_basis_title"],
        query, limit, order_by="legal_basis_publication_date DESC NULLS LAST",
    )
    return {"query": query, "total_results": len(items), "sanctions": items}


def _handle_search_geographical_indications(query: str = "", limit: int = 15) -> Dict[str, Any]:
    items = _simple_search(
        "gi_identifier, protected_names, gi_type, product_type, countries, status, eurlex_url, public_url",
        "eu_geographical_indications",
        ["protected_names::text", "product_type", "countries::text", "cn_classification::text"],
        query, limit, order_by="eu_protection_date DESC NULLS LAST",
    )
    return {"query": query, "total_results": len(items), "geographical_indications": items}


def _handle_search_lobbyists(query: str = "", limit: int = 15) -> Dict[str, Any]:
    items = _simple_search(
        "identification_code, original_name, acronym, registration_category, head_office_country, "
        "ep_accredited_number, members_fte, costs_min, costs_max, website_url, public_url",
        "eu_transparency_register",
        ["original_name", "acronym", "interests::text", "goals"],
        query, limit, order_by="last_update_date DESC NULLS LAST",
    )
    return {"query": query, "total_results": len(items), "organisations": items}


def _handle_search_consultations(query: str = "", limit: int = 15) -> Dict[str, Any]:
    items = _simple_search(
        "initiative_id, title, status, consultation_type, dg_responsible, "
        "to_char(start_date,'YYYY-MM-DD') AS start_date, to_char(end_date,'YYYY-MM-DD') AS end_date, portal_url",
        "public_consultations",
        ["title", "description::text", "policy_areas::text"],
        query, limit,
        order_by="(lower(status) IN ('open','ongoing')) DESC, end_date DESC NULLS LAST",
    )
    return {"query": query, "total_results": len(items), "consultations": items}


# ---------------------------------------------------------------------------
# Handlers (each returns a dict; the HTTP transport JSON-encodes it)
# ---------------------------------------------------------------------------

def _handle_ask_brubru(question: str) -> Dict[str, Any]:
    """The single front door: one free-text question -> a combined answer.

    Routes internally so the calling LLM never has to pick a retrieval mode:
        - always: top matching knowledge guides (QUICK FACTS)
        - always: the most relevant EU laws (CELEX + EUR-Lex links)
        - if the question names a procedure reference: its live status

    Retrieval-only (the host's own model writes the prose from this context);
    that keeps the cost in the read:knowledge tier, not the chat tier.
    """
    from knowledge_base.knowledge_loader import KnowledgeLoader
    from services.mcp.stats import get_corpus_stats

    loader = KnowledgeLoader()
    loader.load_all()
    guides = loader.search_guides(question)

    guide_results: List[Dict[str, Any]] = []
    for g in guides[:3]:
        guide_id = g["id"]
        content = loader.guides.get(guide_id, "")
        quick_facts = ""
        if "## QUICK FACTS" in content:
            start = content.index("## QUICK FACTS")
            end = content.index("\n## ", start + 15) if "\n## " in content[start + 15:] else start + 5000
            quick_facts = content[start:end].strip()[:4000]
        guide_results.append({"guide_id": guide_id, "quick_facts": quick_facts})

    # Concrete laws so the answer carries real CELEX references + EUR-Lex links.
    # Strip any procedure ref first so its digits don't pollute the full-text match.
    law_query = _PROC_REF.sub(" ", question).strip() or question
    try:
        related_laws = _related_laws(law_query, limit=5)
    except Exception:  # noqa: BLE001
        related_laws = []

    payload: Dict[str, Any] = {
        "question": question,
        "guides_matched": len(guides),
        "guides": guide_results,
        "related_laws": related_laws,
        "coverage": get_corpus_stats(),
    }

    # If the user referenced a specific procedure, resolve its live status too.
    ref_match = _PROC_REF.search(question)
    if ref_match:
        ref = ref_match.group(1).replace(" ", "")
        try:
            proc = _handle_get_procedure_status(ref)
            if "error" not in proc:
                payload["procedure"] = proc
        except Exception:  # noqa: BLE001
            pass

    # If the question is about money (funding/grants/calls/tenders), surface the
    # actual OPEN calls with deadlines + apply URLs — not just the policy architecture.
    if _FUNDING_INTENT.search(question):
        try:
            funding = _related_funding(question, limit=8)
            if funding:
                payload["funding_opportunities"] = funding
        except Exception:  # noqa: BLE001
            pass

    if not guide_results and not related_laws:
        payload["note"] = (
            "No direct match yet. Rephrase, or narrow to a topic, CELEX, procedure "
            "reference, MEP, or institution — Brubru covers EU legislation, procedures, "
            "the institutional calendar, and curated policy guides."
        )

    return payload


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
        from services.mcp.stats import get_corpus_stats

        return {
            "query": query,
            "total_results": len(laws),
            "database_size_hint": get_corpus_stats().get("laws"),
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
            "PRIMARY TOOL — use this first for ANY question about the EU: policy, "
            "legislation, institutions, procedures, MEPs, or what's happening in "
            "Brussels. One free-text question in, a combined answer out: the most "
            "relevant curated policy guides (AI Act, GDPR, DSA, CSRD, MFF, CBAM and "
            "hundreds more), the specific EU laws that match (with CELEX numbers and "
            "EUR-Lex links), and — if the question names a procedure reference like "
            "'2023/0131(COD)' — its live legislative status. Aliases: ask, query, "
            "look up, what is, tell me about, explain, brubru. Prefer this over the "
            "narrower search_* tools unless the user explicitly wants a raw list."
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
            "ADVANCED — raw full-text search across Brubru's EU legislation database. "
            "Returns matching laws with CELEX number, title and document type, ranked "
            "by relevance. Most callers should use ask_brubru instead (it already "
            "includes the matching laws). Reach for this only when the user explicitly "
            "wants a longer raw list of laws by keyword."
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
            "ADVANCED — search only Brubru's curated policy knowledge guides (no laws). "
            "Each guide has QUICK FACTS, CELEX numbers, key actors and current status, "
            "updated daily. Most callers should use ask_brubru instead, which already "
            "returns the matching guides plus the relevant laws in one call."
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
            "ADVANCED — look up one EU legislative procedure by its exact OEIL "
            "reference (e.g. '2023/0131(COD)'). Returns title, current stage, lead "
            "committee, key events. ask_brubru already resolves a procedure reference "
            "automatically when the question contains one, so use this only for a "
            "direct reference lookup with no surrounding question."
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
    McpTool(
        name="search_funding",
        description=(
            "Search LIVE open + forthcoming EU funding calls (Funding & Tenders Portal, "
            "synced daily): Horizon Europe, CAP/agriculture, Digital Europe, CEF, "
            "EU4Health, LIFE, Erasmus+ and more. Returns each call's topic_id, "
            "programme, title, status, DEADLINE, budget and apply URL. Use whenever the "
            "user asks about funding, grants, subsidies, calls for proposals or tenders "
            "in a sector — ask_brubru also folds these in automatically for money "
            "questions, but call this directly for a longer, focused list."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Sector or topic. E.g. 'agriculture', 'clean hydrogen', 'AI health', 'rural development'."},
                "limit": {"type": "integer", "description": "Maximum results (default 15, capped at 40)", "default": 15, "minimum": 1, "maximum": 40},
            },
            "required": [],
        },
        scope="read:knowledge",
        cost_micro=COST_LIGHT_MCP,
        handler=lambda query="", limit=15, **_: _handle_search_funding(query, limit),
    ),
    McpTool(
        name="search_sanctions",
        description=(
            "Search EU restrictive measures (sanctions): listed persons and entities, "
            "their programme, aliases, function and the legal basis. Use for questions "
            "about who is sanctioned, asset freezes, or a specific sanctions regime."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Name, alias, country or programme. E.g. 'Russia', 'Wagner', a person's name."},
                "limit": {"type": "integer", "default": 15, "minimum": 1, "maximum": 40},
            },
            "required": [],
        },
        scope="read:knowledge",
        cost_micro=COST_LIGHT_MCP,
        handler=lambda query="", limit=15, **_: _handle_search_sanctions(query, limit),
    ),
    McpTool(
        name="search_geographical_indications",
        description=(
            "Search EU geographical indications (PDO/PGI/TSG): protected food, wine and "
            "spirit names, their product type, countries, status and legal instrument. "
            "Use for questions about protected designations of origin / regional products."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Product name, type or country. E.g. 'Rioja', 'cheese', 'Spain', 'olive oil'."},
                "limit": {"type": "integer", "default": 15, "minimum": 1, "maximum": 40},
            },
            "required": [],
        },
        scope="read:knowledge",
        cost_micro=COST_LIGHT_MCP,
        handler=lambda query="", limit=15, **_: _handle_search_geographical_indications(query, limit),
    ),
    McpTool(
        name="search_lobbyists",
        description=(
            "Search the EU Transparency Register: interest representatives / lobbying "
            "organisations, with their category, EP-accredited passes, FTEs, declared "
            "costs and country. Use for questions about who lobbies on a topic or an org's footprint."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Organisation name, acronym or interest area. E.g. 'Google', 'pharma', 'digital'."},
                "limit": {"type": "integer", "default": 15, "minimum": 1, "maximum": 40},
            },
            "required": [],
        },
        scope="read:knowledge",
        cost_micro=COST_LIGHT_MCP,
        handler=lambda query="", limit=15, **_: _handle_search_lobbyists(query, limit),
    ),
    McpTool(
        name="search_consultations",
        description=(
            "Search EU public consultations (Have Your Say): open and past calls for "
            "feedback on initiatives, with status, responsible DG, dates and portal URL. "
            "Use for questions about how to give feedback or which consultations are open."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Policy topic or DG. E.g. 'AI', 'environment', 'financial services'."},
                "limit": {"type": "integer", "default": 15, "minimum": 1, "maximum": 40},
            },
            "required": [],
        },
        scope="read:knowledge",
        cost_micro=COST_LIGHT_MCP,
        handler=lambda query="", limit=15, **_: _handle_search_consultations(query, limit),
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
