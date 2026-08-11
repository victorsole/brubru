"""Tool surface for the "Brubru DPP" MCP server.

The first per-client, on-demand MCP: a scoped server built for Terraqui and the
LIFE DPP-TEX project (Joana Castella), whose remit is the EU Digital Product
Passport and the textile circularity law around it.

Scope, decided with Victor on 11 Aug 2026:
  * the DPP corpus itself   -> economy_items where body_code='dpp' (122 rows,
    9 resources: the 13 acts with full legal text, sector rollout dates, the
    registry, the six harmonised standards, the 71 battery data points,
    guidance, audience guides, news and events)
  * textile EPR             -> Directive (EU) 2025/1892, already one of the acts
  * consultations           -> the ecodesign/textile slice of Have Your Say,
    including initiative 16116, the ESPR delegated act on apparel textiles
  * the Ecodesign Forum     -> ESPR Art. 19 and its Art. 20 Member States
    Expert Group, from the Commission expert-groups register

`search` and `fetch` are NOT optional extras: ChatGPT's connector requires that
exact pair, so they are implemented here scoped to this corpus rather than the
whole of Brubru.

Every tool reads from the database only. Nothing here calls out to EUR-Lex or
the Commission at request time, so an answer never depends on a third party
being up.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from services.mcp.tools import COST_LIGHT_MCP, McpTool, _get_db

logger = logging.getLogger(__name__)

BODY = "dpp"

# The consultation slice that matters to a textile/ecodesign watcher. Kept as a
# LIKE list rather than a policy-area filter because Have Your Say's own topic
# codes put the textile delegated act under Environment, next to a great deal
# that has nothing to do with products.
_CONSULT_TERMS = ("ecodesign", "textile", "apparel", "product passport",
                  "circular", "waste")


def _rows(sql: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    db = _get_db()
    try:
        return [dict(r._mapping) for r in db.execute(text(sql), params).fetchall()]
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# handlers
# --------------------------------------------------------------------------- #

def _items(item_type: str, q: Optional[str] = None, limit: int = 25,
           with_body: bool = False) -> List[Dict[str, Any]]:
    cols = ("id, title, summary, public_url, document_date"
            + (", body_txt" if with_body else ""))
    sql = (f"SELECT {cols} FROM economy_items "
           "WHERE body_code = :b AND item_type = :t")
    params: Dict[str, Any] = {"b": BODY, "t": item_type, "lim": limit}
    if q:
        sql += " AND (title ILIKE :q OR summary ILIKE :q OR body_txt ILIKE :q)"
        params["q"] = f"%{q}%"
    sql += " ORDER BY document_date DESC NULLS LAST, id LIMIT :lim"
    return _rows(sql, params)


def handle_ask_dpp(question: str) -> Dict[str, Any]:
    """Front door: search every DPP resource at once and say what was found."""
    q = (question or "").strip()
    if not q:
        return {"error": "Ask a question about the digital product passport."}

    found: Dict[str, List[Dict[str, Any]]] = {}
    for t in ("law", "sector", "registry", "standard", "data_point",
              "guidance", "audience", "news", "event"):
        hits = _items(t, q, limit=4)
        if hits:
            found[t] = hits

    consultations = handle_dpp_consultations(query=q, limit=4).get("consultations", [])

    if not found and not consultations:
        return {
            "question": q,
            "found": False,
            "message": (
                "Nothing in the Digital Product Passport corpus matches that. This "
                "server covers the DPP regime, textile extended producer "
                "responsibility, ecodesign consultations and the Ecodesign Forum. "
                "For the wider EU corpus use the main Brubru MCP."
            ),
        }
    return {
        "question": q,
        "found": True,
        "matches": found,
        "consultations": consultations,
        "note": ("Call dpp_law with full_text=true to read an act in full, or "
                 "dpp_when for the date a sector's passport becomes mandatory."),
    }


# An MCP tool result is fed straight into a model's context. The ESPR alone is
# 364,000 characters, about 91,000 tokens, and asking for "textile" with
# full_text returned six acts at once: 285,000 tokens, which no host will accept
# and which would cost more than the answer is worth. Full text is therefore
# capped, and only ever for ONE act at a time.
_TEXT_CAP = 40_000          # ~10k tokens, a comfortable single-response budget
_EXCERPT_WINDOW = 1_200     # characters either side of a `contains` hit
_MAX_EXCERPTS = 12


def _excerpts(body: str, needle: str) -> List[str]:
    """Windows of an act around each mention of `needle`.

    This is what a regulatory lawyer actually asks for: not the whole regulation
    but "what does it say about granularity". Returning windows keeps the answer
    inside a sane context budget and is more useful than the first 40,000
    characters, which is almost always the preamble.
    """
    out: List[str] = []
    low, n = body.lower(), needle.lower()
    start = 0
    while len(out) < _MAX_EXCERPTS:
        i = low.find(n, start)
        if i < 0:
            break
        a = max(0, i - _EXCERPT_WINDOW)
        b = min(len(body), i + len(needle) + _EXCERPT_WINDOW)
        out.append(("..." if a > 0 else "") + body[a:b].strip() + ("..." if b < len(body) else ""))
        start = b
    return out


def handle_dpp_law(query: Optional[str] = None, celex: Optional[str] = None,
                   full_text: bool = False, contains: Optional[str] = None
                   ) -> Dict[str, Any]:
    """The acts that create passport obligations, optionally with their text."""
    want_body = bool(full_text or contains)

    if celex:
        rows = _items("law", celex, limit=3, with_body=want_body)
    elif query:
        rows = _items("law", query, limit=6, with_body=want_body)
    else:
        rows = _items("law", None, limit=25, with_body=False)

    if not want_body:
        for r in rows:
            r.pop("body_txt", None)
        return {
            "count": len(rows), "acts": rows,
            "note": ("Pass celex plus full_text=true to read one act, or "
                     "contains='...' to get only the passages that mention a term."),
        }

    # Body requested. Refuse to return several acts of full text at once.
    if len(rows) > 1:
        for r in rows:
            r.pop("body_txt", None)
        return {
            "count": len(rows), "acts": rows,
            "needs_choice": True,
            "note": (f"{len(rows)} acts match. Full text is returned for one act at "
                     "a time because a single regulation can exceed 90,000 tokens. "
                     "Call again with the celex of the one you want."),
        }
    if not rows:
        return {"count": 0, "acts": [], "note": "No act matches."}

    act = rows[0]
    body = act.pop("body_txt", "") or ""

    if contains:
        windows = _excerpts(body, contains)
        act["excerpts"] = windows
        act["excerpt_count"] = len(windows)
        return {
            "count": 1, "acts": [act],
            "note": (f"{len(windows)} passage(s) of this act mention {contains!r}. "
                     "These are windows around each mention, not the whole act."
                     if windows else
                     f"This act does not mention {contains!r}."),
        }

    truncated = len(body) > _TEXT_CAP
    act["body_txt"] = body[:_TEXT_CAP]
    act["truncated"] = truncated
    act["full_length_chars"] = len(body)
    return {
        "count": 1, "acts": [act],
        "note": (
            f"Showing the first {_TEXT_CAP:,} of {len(body):,} characters. Call again "
            f"with contains='<term>' to get the passages about a specific point "
            "instead of the opening of the act."
            if truncated else "Full legal text of the act."
        ),
    }


def handle_dpp_when(sector: Optional[str] = None) -> Dict[str, Any]:
    rows = _items("sector", sector, limit=25, with_body=True)
    return {
        "count": len(rows),
        "sectors": rows,
        "note": ("Dates are the Commission's indicative rollout unless the summary "
                 "names an article. The only hard deadline in force is 18 February "
                 "2027 for certain large batteries."),
    }


def handle_dpp_data_points(query: Optional[str] = None,
                           battery_type: Optional[str] = None) -> Dict[str, Any]:
    rows = _items("data_point", query, limit=80, with_body=True)
    if battery_type:
        bt = battery_type.strip().lower()
        key = {"ev": "Electric vehicle", "electric vehicle": "Electric vehicle",
               "lmt": "Light means of transport",
               "light means of transport": "Light means of transport",
               "industrial": "Industrial"}.get(bt)
        if key:
            rows = [r for r in rows if key.lower() in (r.get("body_txt") or "").lower()]
    return {
        "count": len(rows),
        "data_points": rows,
        "note": ("The battery passport data points from the Commission guidance of "
                 "28 July 2026. Each body states its legal source in Regulation (EU) "
                 "2023/1542 and its applicability per battery type. Where the source "
                 "PDF layout could not be read unambiguously the body says so: treat "
                 "those as needing a check against the guidance document."),
    }


def handle_dpp_standards() -> Dict[str, Any]:
    rows = _items("standard", None, limit=20, with_body=True)
    return {
        "count": len(rows),
        "standards": rows,
        "note": ("Published by Commission Implementing Decision (EU) 2026/1736. A "
                 "harmonised standard carries a presumption of conformity for the "
                 "requirements it covers."),
    }


def handle_dpp_registry() -> Dict[str, Any]:
    rows = _items("registry", None, limit=20, with_body=True)
    return {
        "count": len(rows),
        "registry": rows,
        "note": ("The registry went live on 20 July 2026. Note that the unique "
                 "registration identifier it returns is explicitly NOT proof of "
                 "compliance (ESPR Article 13(5))."),
    }


def handle_dpp_updates(limit: int = 15) -> Dict[str, Any]:
    news = _items("news", None, limit=limit)
    events = _items("event", None, limit=limit)
    return {"news": news, "events": events,
            "note": "Commission announcements and events on the passport."}


def handle_dpp_consultations(query: Optional[str] = None,
                             status: Optional[str] = None,
                             limit: int = 20) -> Dict[str, Any]:
    """Have Your Say initiatives relevant to ecodesign and textiles."""
    where = ["(" + " OR ".join(f"title ILIKE :t{i}" for i in range(len(_CONSULT_TERMS))) + ")"]
    params: Dict[str, Any] = {f"t{i}": f"%{t}%" for i, t in enumerate(_CONSULT_TERMS)}
    params["lim"] = limit
    if query:
        where.append("(title ILIKE :q OR description ILIKE :q)")
        params["q"] = f"%{query}%"
    if status:
        where.append("status::text = :st")
        params["st"] = status.strip().lower()
    # Order by what a regulatory watcher can still act on: open first, then
    # upcoming, then closed. Sorting on end_date alone buried initiative 16116 --
    # the apparel-textiles delegated act, whose feedback window has no dates yet --
    # below a decade of closed refrigerator measures.
    sql = ("SELECT initiative_id, title, consultation_type::text AS type, "
           "status::text AS status, dg_responsible, start_date, end_date, portal_url "
           "FROM public_consultations WHERE " + " AND ".join(where) +
           " ORDER BY CASE status::text WHEN 'open' THEN 0 WHEN 'upcoming' THEN 1"
           " ELSE 2 END, end_date DESC NULLS LAST, initiative_id DESC LIMIT :lim")
    rows = _rows(sql, params)
    return {
        "count": len(rows),
        "consultations": rows,
        "note": ("Initiative 16116 is the ESPR delegated act on ecodesign "
                 "requirements for sustainable and circular apparel textiles. Its "
                 "feedback period is upcoming, so no dates are set yet."),
    }


def handle_dpp_forum() -> Dict[str, Any]:
    """The Ecodesign Forum and its Member States Expert Group."""
    sql = ("SELECT title, summary, public_url FROM economy_items "
           "WHERE item_type = 'expert_group' AND ("
           "title ILIKE '%ecodesign%' OR title ILIKE '%sustainable product%' "
           "OR title ILIKE '%circular economy%') ORDER BY title LIMIT 15")
    rows = _rows(sql, {})
    return {
        "count": len(rows),
        "groups": rows,
        "note": ("The Ecodesign Forum is the statutory expert group under ESPR "
                 "Article 19; the Member States Expert Group is its subgroup under "
                 "Article 20. This is the channel through which delegated acts are "
                 "prepared, so it is where a sector first sees its future "
                 "requirements."),
    }


# ---- the pair ChatGPT requires -------------------------------------------- #

def handle_search(query: str) -> Dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"results": []}
    rows = _rows(
        "SELECT id, item_type, title, public_url FROM economy_items "
        "WHERE body_code = :b AND (title ILIKE :q OR summary ILIKE :q OR body_txt ILIKE :q) "
        "ORDER BY document_date DESC NULLS LAST, id LIMIT 25",
        {"b": BODY, "q": f"%{q}%"},
    )
    return {"results": [
        {"id": f"dpp:{r['id']}", "title": r["title"], "url": r["public_url"]}
        for r in rows
    ]}


def handle_fetch(id: str) -> Dict[str, Any]:  # noqa: A002 - name fixed by the spec
    raw = (id or "").strip()
    if raw.startswith("dpp:"):
        raw = raw[4:]
    if not raw.isdigit():
        return {"error": f"Unknown id {id!r}. Use an id returned by search."}
    rows = _rows(
        "SELECT id, title, body_txt, public_url, item_type, document_date "
        "FROM economy_items WHERE body_code = :b AND id = :i",
        {"b": BODY, "i": int(raw)},
    )
    if not rows:
        return {"error": f"No DPP item with id {id!r}."}
    r = rows[0]
    body = r["body_txt"] or ""
    # Same cap as dpp_law: fetch on an act was returning 91,000 tokens, which is
    # more than most hosts will accept in a single tool result.
    text_out = body[:_TEXT_CAP]
    meta = {"item_type": r["item_type"],
            "document_date": str(r["document_date"] or "")}
    if len(body) > _TEXT_CAP:
        meta["truncated"] = True
        meta["full_length_chars"] = len(body)
        meta["how_to_read_more"] = (
            "Use dpp_law with this act's celex and contains='<term>' to get the "
            "passages on a specific point rather than the opening of the act."
        )
    return {
        "id": f"dpp:{r['id']}",
        "title": r["title"],
        "text": text_out,
        "url": r["public_url"],
        "metadata": meta,
    }


# --------------------------------------------------------------------------- #
# registry
# --------------------------------------------------------------------------- #

DPP_TOOLS: List[McpTool] = [
    McpTool(
        name="ask_dpp",
        description=(
            "PRIMARY TOOL: ask anything about the EU Digital Product Passport, the "
            "Ecodesign for Sustainable Products Regulation, textile extended "
            "producer responsibility or the ecodesign delegated acts. One "
            "free-text question in, a combined answer out across the acts, the "
            "sector timetable, the registry, the harmonised standards, the battery "
            "data points and the open consultations. Prefer this over the narrower "
            "dpp_* tools unless the user wants one specific list."
        ),
        input_schema={
            "type": "object",
            "properties": {"question": {
                "type": "string",
                "description": "E.g. 'When does the textile passport become mandatory?'",
            }},
            "required": ["question"],
        },
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda question, **_: handle_ask_dpp(question),
    ),
    McpTool(
        name="dpp_law",
        description=(
            "The EU acts that create digital product passport obligations: the ESPR "
            "framework, the implementing regulation for the registry, the "
            "harmonised-standards decision, and the sectoral laws (batteries, "
            "construction products, toys, detergents), plus textile EPR and textile "
            "labelling. For a specific question use contains='<term>' to get just "
            "the passages that address it; use celex + full_text=true to read one "
            "act from the beginning."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free text, e.g. 'registry' or 'textile'."},
                "celex": {"type": "string", "description": "A CELEX number, e.g. 32024R1781."},
                "full_text": {"type": "boolean", "description": "Return the act's text (one act at a time, capped)."},
                "contains": {"type": "string", "description": "Return only the passages of the act that mention this term, e.g. 'granularity' or 'customs'. Preferred over full_text for a specific question."},
            },
        },
        scope="read:laws", cost_micro=COST_LIGHT_MCP,
        handler=lambda query=None, celex=None, full_text=False, contains=None, **_:
            handle_dpp_law(query, celex, bool(full_text), contains),
    ),
    McpTool(
        name="dpp_when",
        description=(
            "When the digital product passport becomes mandatory for a product "
            "group, and under which act. Covers batteries, textiles and apparel, "
            "iron and steel, aluminium, tyres, construction products, furniture, "
            "mattresses, toys, detergents and ICT."
        ),
        input_schema={"type": "object", "properties": {
            "sector": {"type": "string", "description": "E.g. 'textiles', 'batteries'. Omit for all."}}},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda sector=None, **_: handle_dpp_when(sector),
    ),
    McpTool(
        name="dpp_data_points",
        description=(
            "The concrete fields a battery passport must carry: 71 data points, each "
            "with its legal source in Regulation (EU) 2023/1542 and whether it is "
            "mandatory for electric-vehicle, light-means-of-transport or industrial "
            "batteries. This is the schema a passport platform builds against."
        ),
        input_schema={"type": "object", "properties": {
            "query": {"type": "string", "description": "Filter by field name, e.g. 'carbon footprint'."},
            "battery_type": {"type": "string", "description": "ev | lmt | industrial"}}},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda query=None, battery_type=None, **_:
            handle_dpp_data_points(query, battery_type),
    ),
    McpTool(
        name="dpp_standards",
        description=(
            "The six harmonised EN standards for digital product passports whose "
            "references are published in the Official Journal, and which therefore "
            "carry a presumption of conformity: data exchange, unique identifiers, "
            "data carriers, storage and persistence, APIs, and interoperability."
        ),
        input_schema={"type": "object", "properties": {}},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda **_: handle_dpp_standards(),
    ),
    McpTool(
        name="dpp_registry",
        description=(
            "How registration in the central DPP registry works: the production and "
            "testing environments, the two registration pathways, what the unique "
            "registration identifier is and is not, and the customs check at release "
            "for free circulation."
        ),
        input_schema={"type": "object", "properties": {}},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda **_: handle_dpp_registry(),
    ),
    McpTool(
        name="dpp_updates",
        description=(
            "Commission news and events on the digital product passport: what has "
            "moved recently and which webinars are coming."
        ),
        input_schema={"type": "object", "properties": {
            "limit": {"type": "integer", "description": "Max items per list (default 15)."}}},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda limit=15, **_: handle_dpp_updates(int(limit or 15)),
    ),
    McpTool(
        name="dpp_consultations",
        description=(
            "EU public consultations and Have Your Say initiatives on ecodesign, "
            "textiles and circularity, including the ESPR delegated acts. Use this "
            "to answer 'can I still give feedback' and 'what is coming'. Initiative "
            "16116 is the apparel-textiles delegated act."
        ),
        input_schema={"type": "object", "properties": {
            "query": {"type": "string", "description": "Free text filter."},
            "status": {"type": "string", "description": "open | upcoming | closed"}}},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda query=None, status=None, **_:
            handle_dpp_consultations(query, status),
    ),
    McpTool(
        name="dpp_forum",
        description=(
            "The Commission expert groups that prepare ecodesign delegated acts: the "
            "Ecodesign Forum (ESPR Article 19) and its Member States Expert Group "
            "(Article 20). This is where a sector first sees its future requirements."
        ),
        input_schema={"type": "object", "properties": {}},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda **_: handle_dpp_forum(),
    ),
    McpTool(
        name="search",
        description=(
            "Search the Digital Product Passport corpus and return ids, titles and "
            "links. Pair with `fetch` to read an item in full. Required by hosts "
            "that expect the OpenAI search/fetch convention."
        ),
        input_schema={"type": "object",
                      "properties": {"query": {"type": "string"}},
                      "required": ["query"]},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda query, **_: handle_search(query),
    ),
    McpTool(
        name="fetch",
        description=(
            "Fetch one Digital Product Passport item in full by the id returned from "
            "`search`. For an act this returns its complete legal text."
        ),
        input_schema={"type": "object",
                      "properties": {"id": {"type": "string"}},
                      "required": ["id"]},
        scope="read:knowledge", cost_micro=COST_LIGHT_MCP,
        handler=lambda id, **_: handle_fetch(id),  # noqa: A002
    ),
]

_BY_NAME = {t.name: t for t in DPP_TOOLS}


def list_dpp_tools_for_mcp() -> List[Dict[str, Any]]:
    return [{"name": t.name, "description": t.description, "inputSchema": t.input_schema}
            for t in DPP_TOOLS]


def find_dpp_tool(name: str) -> Optional[McpTool]:
    return _BY_NAME.get(name)
