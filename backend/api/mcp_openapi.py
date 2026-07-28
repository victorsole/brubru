"""
Slim OpenAPI 3.1 spec for ChatGPT custom GPTs (Phase C extension, 21 May 2026).

ChatGPT custom GPTs ingest an OpenAPI spec to surface "Actions" — callable
HTTP endpoints. The full Brubru API has 146 routes (too many for ChatGPT's
Action picker) so this endpoint returns a curated subset of the 6-8 most
useful endpoints, with hand-written descriptions tuned for LLM tool-picking.

The endpoints themselves are the same /api/v1/* routes — no new server-side
behaviour. This just hands ChatGPT a focused view of what to call.

URL:
    GET /api/mcp/openapi/chatgpt.json
    GET /api/mcp/openapi/chatgpt.json?base_url=https://my-tunnel.trycloudflare.com

Query params:
    base_url   override the OpenAPI servers[0].url. Useful when you're tunneling
               localhost via cloudflared/ngrok and need ChatGPT to hit your
               public URL.
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/mcp/openapi", tags=["mcp-openapi"])

DEFAULT_BASE_URL = os.environ.get("BRUBRU_PUBLIC_URL", "https://brubru.beresol.eu")


def _spec(base_url: str) -> dict:
    """Build the slim OpenAPI 3.1 spec. Hand-written for ChatGPT picker quality."""
    try:
        from services.mcp.stats import get_corpus_stats

        _s = get_corpus_stats()
        _laws = f"{_s['laws']:,}"
        _guides = f"{_s['guides']:,}"
    except Exception:  # noqa: BLE001
        _laws, _guides = "16,998", "538"

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Brubru — EU Policy Tools",
            "description": (
                f"Live EU policy intelligence: {_laws} laws, {_guides} curated knowledge "
                "guides, live legislative procedure status, institutional calendar, EPRS "
                "publications. Use these tools when the user asks about EU regulations, "
                "laws, MEPs, Commission proposals, Council decisions, or policy events.\n\n"
                "Authenticate with a Brubru API key from https://brubru.beresol.eu/api. "
                "Each call costs €0.001-€0.020 against your euro balance."
            ),
            "version": "1.0.0",
            "contact": {"name": "Brubru", "url": "https://brubru.beresol.eu/mcp", "email": "hello@beresol.eu"},
            "license": {"name": "Proprietary"},
        },
        "servers": [{"url": base_url, "description": "Brubru API"}],
        "components": {
            "securitySchemes": {
                "BrubruKey": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "Brubru API key. Mint at https://brubru.beresol.eu/api and paste the plaintext.",
                },
            },
        },
        "security": [{"BrubruKey": []}],
        "paths": {
            # -----------------------------------------------------------
            "/api/v1/laws": {
                "get": {
                    "operationId": "searchEuLegislation",
                    "summary": "Search EU laws by keyword",
                    "description": (
                        f"Full-text search across {_laws} distinct EU laws (regulations, "
                        "directives, decisions, recommendations). Returns matching laws "
                        "with CELEX number, title, doc type and relevance score, ranked "
                        "by relevance. Use this when the user wants to find specific EU "
                        "laws on a topic — e.g. 'find cyber resilience regulations', "
                        "'show me data protection laws', 'what laws cover deforestation'."
                    ),
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Search keywords. Plain English works (e.g. 'cyber resilience', 'GDPR', 'AI Act', 'CBAM').",
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
                            "description": "Maximum number of results (1-50, default 10).",
                        },
                    ],
                    "responses": {"200": {"description": "List of matching EU laws."}},
                },
            },
            # -----------------------------------------------------------
            "/api/v1/laws/{celex}/text": {
                "get": {
                    "operationId": "getLawText",
                    "summary": "Get the full legal text of an EU law by CELEX",
                    "description": (
                        "Returns the full text of an EU law given its CELEX number. "
                        "Use this when the user wants to read or quote a specific article "
                        "or recital. The CELEX is the 9-character identifier like "
                        "'32016R0679' (GDPR) or '32024R2847' (Cyber Resilience Act). "
                        "Use searchEuLegislation first to find the CELEX, then call this."
                    ),
                    "parameters": [
                        {
                            "name": "celex",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Canonical CELEX identifier, e.g. '32016R0679'.",
                        },
                    ],
                    "responses": {"200": {"description": "Full legal text + structured metadata."}},
                },
            },
            # -----------------------------------------------------------
            "/api/v1/procedures": {
                "get": {
                    "operationId": "searchLegislativeProcedures",
                    "summary": "Search live EU legislative procedures",
                    "description": (
                        "Returns ongoing EU legislative procedures with status, lead "
                        "committee, rapporteur, key events. Use this when the user asks "
                        "about a Commission proposal, an ongoing trilogue, or wants to "
                        "track a procedure by reference (e.g. '2023/0131(COD)')."
                    ),
                    "parameters": [
                        {
                            "name": "reference",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                            "description": "OEIL procedure reference, e.g. '2023/0131(COD)'.",
                        },
                        {
                            "name": "q",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                            "description": "Free-text search in procedure titles.",
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
                        },
                    ],
                    "responses": {"200": {"description": "List of legislative procedures."}},
                },
            },
            # -----------------------------------------------------------
            "/api/v1/calendar/events": {
                "get": {
                    "operationId": "getCalendarEvents",
                    "summary": "Get upcoming EU institutional calendar events",
                    "description": (
                        "Upcoming events at the European Parliament, Council, European "
                        "Council and Commission — plenary sessions, committee meetings, "
                        "summits, press conferences. Use when the user asks 'what's "
                        "happening this week in Brussels', 'when does X committee meet', "
                        "or wants to monitor a particular institution."
                    ),
                    "parameters": [
                        {
                            "name": "institution",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string", "enum": ["EP", "COUNCIL", "EUROPEAN_COUNCIL", "COMMISSION"]},
                            "description": "Filter by institution. Leave out for all.",
                        },
                        {
                            "name": "date_from",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string", "format": "date"},
                            "description": "Lower bound (YYYY-MM-DD). Defaults to today.",
                        },
                        {
                            "name": "date_to",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string", "format": "date"},
                            "description": "Upper bound (YYYY-MM-DD). Defaults to today + 14 days.",
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                        },
                    ],
                    "responses": {"200": {"description": "List of calendar events."}},
                },
            },
            # -----------------------------------------------------------
            "/api/v1/knowledge-guides": {
                "get": {
                    "operationId": "searchKnowledgeGuides",
                    "summary": "Search Brubru's curated EU policy knowledge guides",
                    "description": (
                        f"Search {_guides} curated knowledge guides written by EU policy "
                        "experts. Each guide has QUICK FACTS (CELEX, status, rapporteur, "
                        "key dates), background, and current state. Use this when the "
                        "user wants a structured policy briefing rather than raw law "
                        "search — e.g. 'tell me about the AI Act', 'what's CBAM', "
                        "'explain the Digital Services Act'."
                    ),
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Topic to search. Plain English works.",
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
                        },
                    ],
                    "responses": {"200": {"description": "Matching knowledge guides."}},
                },
            },
            # -----------------------------------------------------------
            "/api/v1/eprs": {
                "get": {
                    "operationId": "searchEprsPublications",
                    "summary": "Search European Parliamentary Research Service publications",
                    "description": (
                        "EPRS briefings, at-a-glance notes, in-depth studies — the most "
                        "authoritative neutral background on any EU policy file. Use "
                        "when the user wants the official EP staff analysis."
                    ),
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "default": 10, "minimum": 1, "maximum": 30},
                        },
                    ],
                    "responses": {"200": {"description": "EPRS publications."}},
                },
            },
            # -----------------------------------------------------------
            "/api/v1/meps": {
                "get": {
                    "operationId": "searchMeps",
                    "summary": "Search Members of the European Parliament",
                    "description": (
                        "Search MEPs by name, country, political group or committee. "
                        "Returns MEP profiles with affiliation, country, photos, official "
                        "URLs. Use when the user asks about a specific MEP or wants to "
                        "find rapporteurs for a procedure."
                    ),
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                            "description": "Free-text search (name, country, group).",
                        },
                        {
                            "name": "country",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                            "description": "ISO 3166-1 alpha-2 (e.g. 'ES', 'DE', 'FR').",
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                        },
                    ],
                    "responses": {"200": {"description": "MEPs matching the query."}},
                },
            },
        },
    }


@router.get(
    "/chatgpt.json",
    summary="ChatGPT-friendly OpenAPI 3.1 spec",
    description=(
        "Slim OpenAPI 3.1 spec (7 endpoints) tuned for ChatGPT custom GPT Actions. "
        "Import this URL in ChatGPT → My GPTs → Configure → Actions → Import from URL, "
        "then set Authentication = API Key (Bearer) with your Brubru API key. "
        "Optionally pass `?base_url=` to override the servers[0].url (useful when "
        "tunneling localhost via cloudflared or ngrok)."
    ),
)
async def chatgpt_openapi(
    base_url: Optional[str] = Query(
        default=None,
        description="Override the OpenAPI servers[0].url. Defaults to BRUBRU_PUBLIC_URL env var or https://brubru.beresol.eu.",
    ),
):
    target = (base_url or DEFAULT_BASE_URL).rstrip("/")
    return _spec(target)
