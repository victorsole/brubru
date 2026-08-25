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
    # Generic legal-English added 25 Aug 2026. The OR fallback below ranks by
    # full-text hits, and EU law is full of acts whose TITLE is built from these
    # words -- there are thousands of "Regulation ... IMPOSING a definitive
    # countervailing DUTY on imports of ...". Asking "which ARTICLE of the Cyber
    # Resilience Act IMPOSES the 24-hour REPORTING DUTY" therefore returned a
    # countervailing duty on sulphanilic acid from India as the top related law.
    # Confidently irrelevant, on the surface we are about to market.
    "article", "articles", "duty", "duties", "impose", "imposes", "imposing",
    "report", "reports", "reporting", "requirement", "requirements", "obligation",
    "obligations", "provision", "provisions", "rule", "rules", "apply", "applies",
    "applying", "says", "state", "states", "means", "meaning", "hour", "hours",
    "day", "days", "deadline", "deadlines", "notify", "notification", "notifications",
    "regulation", "directive", "decision", "law", "laws", "legal", "union",
    "european", "europe", "commission", "council", "parliament", "member",
}

# A rank threshold was tried here and removed the same afternoon. Calibrated on
# five sample queries it dropped genuinely relevant results (CBAM implementing
# regulations at 0.041, payment-services acts at 0.038) while adding nothing the
# stop-list above had not already fixed. A blunt cut-off tuned on a handful of
# examples is the kind of check that fails in a direction nobody notices, which
# is precisely what this file was being audited for.

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
                ORDER BY rank DESC,
                         -- A corrigendum carries the same words as the act it
                         -- corrects, so it ties on rank and can win on nothing
                         -- but row order. The act itself is what a reader wants
                         -- named first.
                         (title ILIKE 'Corrigendum%') ASC,
                         celex ASC
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
# Generic gateway — reach ANY of Brubru's v2 endpoints through 2 tools, so the
# whole API is callable without hundreds of per-endpoint tools. Runs a blocking
# self-HTTP call (urllib, stdlib) which is safe because mcp_http runs tool
# handlers off the event loop.
#
# The self-call needs an API key that is billing-exempt, so the gateway call is
# charged ONCE (at the MCP tool layer), not twice. Two ways it gets one:
#   1. BRUBRU_INTERNAL_API_KEY env var — a dedicated admin/service key (the
#      production path; covers gateway calls from any caller).
#   2. The caller's OWN key, forwarded by mcp_http *only when the caller is an
#      admin* (admin v2 calls are debit-exempt, so no double-billing). This lets
#      an operator use the gateway with zero server config.
# Set via set_gateway_caller_key() before invoke_tool(); read in _self_get().
# ---------------------------------------------------------------------------

import contextvars as _contextvars

_V2_PREFIX = "/api/v2/"

# Response-size guards for the generic gateway, so a model calling a large
# endpoint cannot flood its own context. A default `limit` keeps list endpoints
# small (endpoints that do not declare `limit` ignore it — FastAPI drops unknown
# query params); the raw byte ceiling is a hard backstop against multi-MB bodies;
# the data[] trim keeps an oversized paginated envelope useful instead of erroring.
_GATEWAY_DEFAULT_LIMIT = 25
_GATEWAY_MAX_BYTES = 400_000       # hard read ceiling for a single gateway call
_GATEWAY_MAX_DATA_ITEMS = 25       # keep at most this many items from an envelope's data[]
_GATEWAY_SOFT_JSON = 180_000       # if the serialized result still exceeds this, trim harder
_LIMIT_PARAM_KEYS = ("limit", "page_size", "per_page", "size")

# Forwarded caller key for the gateway self-call (admin-only; see above). A
# ContextVar so it is per-request and propagates into the worker thread that
# anyio.to_thread.run_sync uses to run the handler.
_GATEWAY_CALLER_KEY: "_contextvars.ContextVar[str]" = _contextvars.ContextVar(
    "mcp_gateway_caller_key", default=""
)


def set_gateway_caller_key(key: str) -> None:
    """mcp_http calls this before dispatch to forward an ADMIN caller's key to
    the gateway self-call. No-op safe with an empty string."""
    _GATEWAY_CALLER_KEY.set(key or "")


def _self_get(path: str, params: Optional[Dict[str, Any]], authed: bool = True,
              max_bytes: Optional[int] = None) -> Dict[str, Any]:
    import os
    import json as _json
    import urllib.error
    import urllib.parse
    import urllib.request

    base = os.environ.get("BRUBRU_PUBLIC_URL", "https://brubru-production.up.railway.app").rstrip("/")
    qs = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
    url = base + path + (("?" + qs) if qs else "")
    req = urllib.request.Request(url, method="GET")
    if authed:
        # Production path: dedicated admin/service key. Fallback: the admin
        # caller's own key, forwarded by mcp_http (admin v2 calls are debit-
        # exempt, so still single-billed). See the section header above.
        key = os.environ.get("BRUBRU_INTERNAL_API_KEY", "") or _GATEWAY_CALLER_KEY.get("")
        if not key:
            return {"error": "gateway_unconfigured",
                    "detail": ("The gateway needs a billing-exempt key. Either set "
                               "BRUBRU_INTERNAL_API_KEY on the server, or call as an admin "
                               "(your key is then forwarded automatically).")}
        req.add_header("X-API-Key", key)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            # Read one byte past the ceiling so we can detect (and report) overflow
            # without pulling a multi-MB body into the model's context.
            data = resp.read(max_bytes + 1) if max_bytes else resp.read()
            status = resp.getcode()
    except urllib.error.HTTPError as e:
        data, status = e.read(), e.code            # error bodies are small; read in full
    except Exception as exc:  # noqa: BLE001
        return {"error": "gateway_call_failed", "detail": str(exc)[:200], "path": path}
    over = bool(max_bytes) and len(data) > max_bytes
    raw = (data[:max_bytes] if max_bytes else data).decode("utf-8", "replace")
    if over:
        return {"http_status": status, "path": path, "truncated": True,
                "detail": (f"Response exceeded {max_bytes // 1000} KB and was cut off. "
                           "Re-call with a smaller 'limit', add filters, or paginate with 'page'."),
                "preview": raw[:1500]}
    try:
        body = _json.loads(raw)
    except Exception:  # noqa: BLE001
        body = {"raw": raw[:2000]}
    return {"http_status": status, "path": path, "body": body}


def _gateway_trim_result(res: Dict[str, Any]) -> Dict[str, Any]:
    """Keep an oversized paginated envelope useful: trim its data[] list and note it.

    Complements the raw byte ceiling in _self_get — that stops multi-MB bodies;
    this stops a merely-large in-limit envelope (or one from an endpoint that
    ignored the injected limit) from still swamping the model context.
    """
    import json as _json
    if not isinstance(res, dict) or not isinstance(res.get("body"), dict):
        return res
    body = res["body"]
    data = body.get("data")
    if isinstance(data, list) and len(data) > _GATEWAY_MAX_DATA_ITEMS:
        body["_gateway_note"] = (
            f"Showing the first {_GATEWAY_MAX_DATA_ITEMS} of {len(data)} items to fit the "
            "model context. Pass a larger 'limit' or use 'page' for more.")
        body["data"] = data[:_GATEWAY_MAX_DATA_ITEMS]
    try:  # final serialized-size backstop for big per-item bodies
        if len(_json.dumps(res)) > _GATEWAY_SOFT_JSON and isinstance(body.get("data"), list):
            keep = max(1, _GATEWAY_MAX_DATA_ITEMS // 3)
            body["data"] = body["data"][:keep]
            note = body.get("_gateway_note", "")
            body["_gateway_note"] = (note + f" Response still large; further trimmed to {keep} items.").strip()
    except Exception:  # noqa: BLE001
        pass
    return res


def _handle_query_brubru_api(path: str = "", params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Call any Brubru v2 GET endpoint (from list_brubru_datasets) and return its JSON.

    Guards the model's context: injects a default `limit` when the caller gave
    none (list endpoints stay small; endpoints without a `limit` param ignore it),
    caps the raw response at _GATEWAY_MAX_BYTES, and trims an oversized envelope's
    data[]. If the injected limit trips an endpoint whose own max is below the
    default (HTTP 422), it retries once with the caller's original params.
    """
    p = (path or "").strip()
    if not p:
        return {"error": "invalid_path", "detail": "Provide a v2 path, e.g. /api/v2/funding/funding-opportunities"}
    if not p.startswith("/"):
        p = "/" + p
    if not p.startswith(_V2_PREFIX):
        p = _V2_PREFIX + p.lstrip("/")
    if ".." in p:
        return {"error": "invalid_path"}

    params = dict(params) if isinstance(params, dict) else {}
    injected = False
    if not any(k in params for k in _LIMIT_PARAM_KEYS):
        params["limit"] = _GATEWAY_DEFAULT_LIMIT
        injected = True
    res = _self_get(p, params, authed=True, max_bytes=_GATEWAY_MAX_BYTES)
    # An endpoint whose limit cap is below our default (or that rejects the param)
    # returns 422 — retry once with the endpoint's own default instead.
    if injected and isinstance(res, dict) and res.get("http_status") == 422:
        params.pop("limit", None)
        res = _self_get(p, params, authed=True, max_bytes=_GATEWAY_MAX_BYTES)
    return _gateway_trim_result(res)


def _handle_list_brubru_datasets(filter: str = "", limit: int = 60) -> Dict[str, Any]:
    """Browse the whole v2 API catalogue (GET endpoints: path + summary), filterable."""
    res = _self_get("/api/v2/openapi.json", {}, authed=False)
    spec = res.get("body") if isinstance(res, dict) else None
    if not isinstance(spec, dict) or "paths" not in spec:
        return {"error": "catalogue_unavailable", "detail": res}
    f = (filter or "").lower()
    cap = max(1, min(int(limit or 60), 200))
    endpoints: List[Dict[str, Any]] = []
    for path, item in spec["paths"].items():
        if not isinstance(item, dict) or "get" not in item:
            continue
        summary = (item["get"] or {}).get("summary", "")
        if f and f not in path.lower() and f not in (summary or "").lower():
            continue
        endpoints.append({"path": path, "summary": summary})
        if len(endpoints) >= cap:
            break
    return {
        "filter": filter,
        "total": len(endpoints),
        "endpoints": endpoints,
        "next": "Pass any 'path' to query_brubru_api with optional params to fetch the data.",
    }


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


# ---------------------------------------------------------------------------
# OpenAI Deep Research / "company knowledge" standard tools: search + fetch.
# ChatGPT's Deep Research and company-knowledge connectors require a tool named
# `search(query)` returning {results:[{id,title,url}]} and a `fetch(id)`
# returning the full document {id,title,text,url,metadata}. We map both onto
# Brubru's knowledge guides + eu_laws so Brubru is usable as a ChatGPT knowledge
# source. The richer `ask_brubru` tool stays for hosts that allow arbitrary tools.
# ---------------------------------------------------------------------------

_GUIDE_URL_BASE = "https://brubru.beresol.eu/api/v2/proprietary/guides/"


def _first_heading(content: str, fallback: str) -> str:
    """First real title line: skip blanks, YAML frontmatter fences and Markdown
    horizontal rules ('---', '***', '___') so we never title a guide '---'."""
    for line in (content or "").lstrip().splitlines():
        s = line.strip()
        if not s:
            continue
        if set(s) <= {"-", "*", "_"}:  # ---, ***, ___ (frontmatter / rule)
            continue
        if s.lower().startswith("title:"):  # YAML frontmatter title
            val = s.split(":", 1)[1].strip().strip('"\'')
            if val:
                return val
            continue
        title = s.lstrip("#").strip()
        if title:
            return title
    return fallback


def _handle_search(query: str = "", limit: int = 10) -> Dict[str, Any]:
    """OpenAI Deep Research `search`: {results:[{id,title,url}]} over guides + laws."""
    q = (query or "").strip()
    results: List[Dict[str, Any]] = []
    if not q:
        return {"results": results}
    try:
        from knowledge_base.knowledge_loader import KnowledgeLoader

        loader = KnowledgeLoader()
        loader.load_all()
        for g in loader.search_guides(q)[:5]:
            gid = g["id"]
            content = loader.guides.get(gid, "")
            results.append({
                "id": f"guide:{gid}",
                "title": _first_heading(content, gid),
                "url": _GUIDE_URL_BASE + gid,
            })
    except Exception:  # noqa: BLE001
        pass
    try:
        for law in _handle_search_eu_legislation(q, limit=5).get("laws", []):
            celex = law.get("celex")
            if not celex:
                continue
            results.append({
                "id": f"law:{celex}",
                "title": law.get("title") or celex,
                "url": law.get("url"),
            })
    except Exception:  # noqa: BLE001
        pass
    cap = max(1, min(int(limit or 10), 20))
    return {"results": results[:cap]}


def _handle_fetch(id: str = "") -> Dict[str, Any]:  # noqa: A002 (name fixed by the OpenAI schema)
    """OpenAI Deep Research `fetch`: {id,title,text,url,metadata} for one result id."""
    rid = (id or "").strip()
    if rid.startswith("guide:"):
        gid = rid.split(":", 1)[1]
        try:
            from knowledge_base.knowledge_loader import KnowledgeLoader

            loader = KnowledgeLoader()
            loader.load_all()
            content = loader.guides.get(gid)
            if content:
                return {
                    "id": rid,
                    "title": _first_heading(content, gid),
                    "text": content,
                    "url": _GUIDE_URL_BASE + gid,
                    "metadata": {"type": "knowledge_guide", "guide_id": gid},
                }
        except Exception:  # noqa: BLE001
            pass
        return {"id": rid, "title": gid, "text": "", "url": _GUIDE_URL_BASE + gid,
                "metadata": {"type": "knowledge_guide", "error": "not_found"}}
    if rid.startswith("law:"):
        celex = rid.split(":", 1)[1]
        url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
        db = _get_db()
        try:
            row = db.execute(
                text("SELECT title, COALESCE(doc_type_normalized, doc_type) FROM eu_laws WHERE celex = :c LIMIT 1"),
                {"c": celex},
            ).fetchone()
        finally:
            db.close()
        if row:
            title = row[0] or celex
            body = (f"{title}\n\nDocument type: {row[1] or 'n/a'}\nCELEX: {celex}\n"
                    f"Full text on EUR-Lex: {url}")
            return {"id": rid, "title": title, "text": body, "url": url,
                    "metadata": {"type": "eu_law", "celex": celex, "doc_type": row[1]}}
        return {"id": rid, "title": celex, "text": f"See EUR-Lex: {url}", "url": url,
                "metadata": {"type": "eu_law", "celex": celex}}
    return {"id": rid, "title": rid, "text": "", "url": None, "metadata": {"error": "unknown_id"}}


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
    McpTool(
        name="list_brubru_datasets",
        description=(
            "Browse Brubru's FULL EU data API catalogue (900+ GET endpoints across 80+ "
            "domains: legislation, procedures, MEPs, votes, committees, calendar, funding, "
            "tenders, sanctions, GIs, lobbyists, consultations, trade, cohesion, agencies, "
            "and much more). Returns matching endpoint paths + summaries. Use this to "
            "discover what data exists, then call query_brubru_api with a path. Filter by "
            "keyword to narrow (e.g. 'votes', 'agriculture', 'infringement')."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "filter": {"type": "string", "description": "Keyword to match on endpoint path or summary. Empty = first 60 endpoints."},
                "limit": {"type": "integer", "default": 60, "minimum": 1, "maximum": 200},
            },
            "required": [],
        },
        scope="read:knowledge",
        cost_micro=COST_LIGHT_MCP,
        handler=lambda filter="", limit=60, **_: _handle_list_brubru_datasets(filter, limit),
    ),
    McpTool(
        name="query_brubru_api",
        description=(
            "Call ANY Brubru v2 GET endpoint by path and return its live JSON — the "
            "universal gateway to all of Brubru's EU data. First use list_brubru_datasets "
            "to find the path, then call this. Example: path='/api/v2/funding/"
            "funding-opportunities', params={'programme':'Horizon','status':'open'}. Use "
            "when a dedicated tool (ask_brubru, search_funding, ...) doesn't cover the exact "
            "dataset the user needs."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "A v2 path from list_brubru_datasets, e.g. '/api/v2/legislative/eur-lex/laws'."},
                "params": {"type": "object", "description": "Optional query parameters as key/value pairs, e.g. {'q':'AI','limit':10}."},
            },
            "required": ["path"],
        },
        scope="read:knowledge",
        cost_micro=COST_LIGHT_MCP,
        handler=lambda path="", params=None, **_: _handle_query_brubru_api(path, params),
    ),
    # OpenAI Deep Research / ChatGPT "company knowledge" standard pair. Names are
    # fixed by OpenAI's schema ("search" + "fetch"). search returns lightweight
    # {id,title,url} hits; fetch returns the full document for a chosen id.
    McpTool(
        name="search",
        description=(
            "Search Brubru's EU policy knowledge (curated guides + EU legislation) and "
            "return a ranked list of results, each with an id, title and URL. Follow up "
            "with `fetch` on a result id to read the full document. This is the standard "
            "search entry point for Deep Research / company-knowledge use; for a single "
            "combined answer, `ask_brubru` is richer."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms, e.g. 'AI Act obligations' or 'CBAM steel'."},
            },
            "required": ["query"],
        },
        scope="read:knowledge",
        cost_micro=COST_LIGHT_MCP,
        handler=lambda query="", limit=10, **_: _handle_search(query, limit),
    ),
    McpTool(
        name="fetch",
        description=(
            "Fetch the full text of one Brubru knowledge result by its id (as returned "
            "by `search` — 'guide:<slug>' for a policy guide or 'law:<CELEX>' for an EU "
            "law). Returns id, title, full text, URL and metadata."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "A result id from `search`, e.g. 'guide:ai_act_regulation' or 'law:32016R0679'."},
            },
            "required": ["id"],
        },
        scope="read:knowledge",
        cost_micro=COST_LIGHT_MCP,
        handler=lambda id="", **_: _handle_fetch(id),
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
