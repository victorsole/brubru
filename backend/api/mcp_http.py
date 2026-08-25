"""
Brubru MCP — HTTP transport (Phase C, 21 May 2026).

Public Model Context Protocol endpoint at POST /api/mcp.

Speaks JSON-RPC 2.0 per the MCP spec
(https://spec.modelcontextprotocol.io/). Supported methods:

    initialize                  — capability handshake (free, no debit)
    notifications/initialized   — client ready signal (no response)
    tools/list                  — return tool catalogue (free, no debit)
    tools/call                  — invoke a tool (scope-checked + per-call debit)

Authentication (any one of):
    Authorization: Bearer brubru_live_...   (preferred, most secure)
    X-API-Key:    brubru_live_...           (also accepted, mirror REST)
    ?key=brubru_live_...  /  ?api_key=...   (query string; for one-URL hosts
                                             like the claude.ai web connector)

The same ApiKey scopes + balance system as the REST surface. Each tool in
services/mcp/tools.py declares its required scope (read:laws, read:ep, ...)
and per-call cost in micro-euros.

Per-tool-call lifecycle:
    1. Resolve api_key from headers (auth_api_key.get_api_user logic, reused).
    2. Look up the tool by name (`tools/call` payload).
    3. Check the api_key has the tool's scope (api_key.grants_scope).
    4. Atomic balance debit via services/billing/api_meter.debit.
    5. Call the handler. If it raises -> refund the debit + record_usage(refunded=True).
    6. Wrap the result in MCP tool-content envelope.

Sandbox keys (is_sandbox=True) bypass user-balance debit and use the shared
api_sandbox_pool counter instead, same as REST.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import anyio

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import SessionLocal
from models.api_key import ApiKey, KEY_PREFIX
from models.user import User
from services.billing.api_meter import (
    debit,
    mark_event_refunded,
    record_usage,
    is_probe_header,
    refund,
    sandbox_consume,
    set_event_status,
)
from services.mcp.tools import (
    TOOLS,
    McpTool,
    find_tool,
    invoke_tool,
    list_tools_for_mcp,
    set_gateway_caller_key,
)

logger = logging.getLogger(__name__)

# /api/mcp keeps the public surface under the existing /api/* prefix so vite
# proxies it the same way as REST endpoints and Stripe webhooks already work.
# `router` is built at the bottom of this module by make_mcp_router().

# JSON-RPC application error codes (-32000 to -32099 are app-defined).
_ERR_AUTH_MISSING = -32001
_ERR_AUTH_INVALID = -32002
_ERR_KEY_EXPIRED = -32003
_ERR_SCOPE_MISSING = -32004
_ERR_INSUFFICIENT_BALANCE = -32005
_ERR_SANDBOX_CAPPED = -32006
_ERR_TOOL_NOT_FOUND = -32007
_ERR_TOOL_HANDLER_FAILED = -32008

# Server capabilities reported in `initialize`.
# MINIMAL by design: name + version only. Extra Implementation fields (icons,
# websiteUrl, title) were added 30 Jul and immediately broke the claude.ai
# connector — its client validates the initialize result against a schema that
# rejected the unknown fields, treated the server as invalid, and fell back to
# an OAuth-registration flow ("Couldn't register with Brubru's sign-in service").
# Connector branding comes from the ORIGIN FAVICON (main.py /favicon.ico), which
# is the host-agnostic mechanism. Do NOT add non-core fields here without
# testing the real claude.ai connector first.
SERVER_INFO = {
    "name": "Brubru",
    "version": "1.0.0",
}
PROTOCOL_VERSION = "2024-11-05"  # MCP spec version we implement


# ---------------------------------------------------------------------------
# Profiles — one transport, several named MCP servers
# ---------------------------------------------------------------------------
# A profile is everything that differs between one mounted MCP and another:
# the name the host displays, the tool subset, and the instructions block.
# Everything else (auth, billing, the JSON-RPC envelope and above all the
# `initialize` handshake) stays shared, because that handshake is the piece
# that once broke the claude.ai connector by carrying a single extra field.
# Duplicating it per client MCP would mean duplicating that landmine.
@dataclass(frozen=True)
class McpProfile:
    server_info: Dict[str, str]
    list_tools: Callable[[], List[Dict[str, Any]]]
    find_tool: Callable[[str], Optional[McpTool]]
    tool_count: Callable[[], int]
    instructions: Callable[[str], str]


def _default_instructions(coverage: str) -> str:
    return (
        "Brubru is EU policy intelligence for any AI assistant. For almost any "
        "question, call the single tool `ask_brubru` with the user's question — "
        "it returns the matching policy guides, the relevant EU laws (with CELEX "
        "and EUR-Lex links), and live procedure status in one call. The other "
        "tools (calendar events, EPRS, raw law/guide search) are advanced and "
        "rarely needed.\n\n"
        f"Live coverage: {coverage}.\n\n"
        "Each call is metered in euros against your Brubru API balance; mint a "
        "key and top up at https://brubru.beresol.eu/api."
    )


DEFAULT_PROFILE = McpProfile(
    server_info=SERVER_INFO,
    list_tools=lambda: list_tools_for_mcp(),
    find_tool=lambda name: find_tool(name),
    tool_count=lambda: len(TOOLS),
    instructions=_default_instructions,
)


# ---------------------------------------------------------------------------
# Auth resolution (reuses the same logic as auth_api_key.get_api_user but
# returns the ApiKey + User pair rather than raising HTTPException, so we can
# emit JSON-RPC errors instead of HTTP errors).
# ---------------------------------------------------------------------------

def _extract_key(
    authorization: Optional[str],
    x_api_key: Optional[str],
    query_key: Optional[str] = None,
) -> Optional[str]:
    """Resolve the plaintext API key from, in order of preference:
        1. Authorization: Bearer <key>   (most secure)
        2. X-API-Key: <key>
        3. ?key=<key> / ?api_key=<key>   (query string)

    Header auth is preferred, but many MCP hosts (notably the claude.ai web
    custom-connector UI) only let the user enter a URL, with no field for a
    header. For those, the key rides in the query string -- the same pattern
    Tavily's hosted MCP uses (mcp.tavily.com/mcp/?tavilyApiKey=...). Less
    private (URLs can land in logs/history) so OAuth is the eventual answer,
    but it makes one-URL hosts work today.
    """
    if authorization:
        parts = authorization.strip().split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
    if x_api_key:
        return x_api_key.strip()
    if query_key:
        return query_key.strip()
    return None


def _resolve_api_key(
    db: Session, plaintext: str
) -> Tuple[Optional[ApiKey], Optional[User], Optional[Tuple[int, str]]]:
    """Return (api_key, user, error). error is (code, message) or None on success."""
    if not plaintext:
        return None, None, (_ERR_AUTH_MISSING, "Missing API key. Send Authorization: Bearer brubru_live_... or X-API-Key: ...")
    if not plaintext.startswith(KEY_PREFIX):
        # Not a brubru_live_ key — maybe an OAuth access token (Option B). Resolve
        # it to the ApiKey it was minted against, so scope + billing are unchanged.
        try:
            from api.mcp_oauth import resolve_oauth_access_token
            oauth_key, oauth_user = resolve_oauth_access_token(db, plaintext)
        except Exception:  # noqa: BLE001
            oauth_key, oauth_user = None, None
        if oauth_key is not None:
            return oauth_key, oauth_user, None
        return None, None, (_ERR_AUTH_INVALID, "Invalid credentials. Use a brubru_live_ key or an OAuth access token.")

    key_hash = ApiKey.hash_plaintext(plaintext)
    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
        .first()
    )
    if api_key is None:
        return None, None, (_ERR_AUTH_INVALID, "API key not found or revoked.")
    if api_key.is_expired:
        return None, None, (_ERR_KEY_EXPIRED, "API key has expired. Mint a new one at brubru.beresol.eu/api.")
    user = db.query(User).filter(User.id == api_key.user_id).first()
    if user is None or not user.is_active:
        return None, None, (_ERR_AUTH_INVALID, "API key owner is inactive.")
    _touch_last_used(db, api_key)
    return api_key, user, None


def _touch_last_used(db: Session, api_key: ApiKey) -> None:
    """Record that this key was just used.

    The REST path (api/auth_api_key.py) has always done this via a background
    task; the MCP path never did, so a key used exclusively through MCP read
    `last_used_at = NULL` no matter how much traffic it carried. Measured
    25 Aug 2026: 23 keys had usage events, only 14 had the column set, and the
    gap was the MCP-only callers. One client's key showed "never used" against
    178 recorded calls -- the kind of instrument that answers a question wrongly
    rather than admitting it does not know.

    Throttled to once a minute: MCP clients fire many small calls per session
    and the exact second is worth nothing. Failure here must never break the
    call -- knowing when a key was last used is strictly less important than
    the request working -- so it degrades to a log line on its own connection
    state rather than poisoning the caller's transaction.
    """
    try:
        now = datetime.now(timezone.utc)
        previous = api_key.last_used_at
        if previous is not None:
            if previous.tzinfo is None:
                previous = previous.replace(tzinfo=timezone.utc)
            if (now - previous).total_seconds() < 60:
                return
        api_key.last_used_at = now
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[mcp] could not update last_used_at for key %s: %s: %s",
                       getattr(api_key, "key_prefix", "?"), type(exc).__name__, exc)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# JSON-RPC envelope helpers
# ---------------------------------------------------------------------------

def _ok(req_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    e: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        e["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": e}


def _tool_text_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap a handler return-value as an MCP `tools/call` result.

    Carries BOTH representations: `content` (text JSON — every MCP client reads
    this) and `structuredContent` (the raw object — MCP spec 2025-06-18; OpenAI
    Deep Research / ChatGPT inspect it directly, e.g. the `search` results array).
    structuredContent must be a JSON object, so non-dict payloads are wrapped.
    """
    structured = payload if isinstance(payload, dict) else {"result": payload}
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False, default=str),
            }
        ],
        "structuredContent": structured,
        "isError": False,
    }


# ---------------------------------------------------------------------------
# Method dispatch
# ---------------------------------------------------------------------------

def _dispatch_initialize(req_id: Any, params: Dict[str, Any],
                         profile: "McpProfile") -> Dict[str, Any]:
    """Capability handshake.

    Per MCP spec the server should respond with the highest mutually-supported
    protocol version. To maximise compatibility with newer Claude Desktop /
    Cursor / Cline builds that send `2025-11-25` or similar, we echo back the
    client's requested version if it looks like a valid date (YYYY-MM-DD).
    The client decides whether to proceed; if not, we fall back to our hard
    minimum (PROTOCOL_VERSION) on the next request. Old clients that send the
    older version we already advertised still work because we'd never go
    BELOW our hardcoded minimum.
    """
    import re as _re

    client_protocol = (params or {}).get("protocolVersion") if isinstance(params, dict) else None
    if isinstance(client_protocol, str) and _re.fullmatch(r"\d{4}-\d{2}-\d{2}", client_protocol):
        # Use the client's version (>= our hardcoded minimum is the realistic case;
        # if client somehow sends an older version we still happily speak it since
        # the server's behaviour is the same regardless of version label).
        protocol = client_protocol
    else:
        protocol = PROTOCOL_VERSION

    try:
        from services.mcp.stats import format_summary

        coverage = format_summary()
    except Exception:  # noqa: BLE001
        coverage = "EU laws, knowledge guides, procedures, calendar events, EPRS publications"

    return _ok(
        req_id,
        {
            "protocolVersion": protocol,
            "serverInfo": profile.server_info,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "instructions": profile.instructions(coverage),
        },
    )


def _dispatch_tools_list(req_id: Any, profile: "McpProfile") -> Dict[str, Any]:
    return _ok(req_id, {"tools": profile.list_tools()})


async def _dispatch_tools_call(
    req_id: Any,
    params: Dict[str, Any],
    db: Session,
    api_key: ApiKey,
    user: User,
    client_ip: Optional[str],
    request_id: str,
    caller_key: Optional[str] = None,
    profile: "McpProfile" = None,
    is_probe: bool = False,
) -> Dict[str, Any]:
    tool_name = params.get("name") if params else None
    arguments = params.get("arguments") if params else None
    if not isinstance(tool_name, str) or not tool_name:
        return _err(req_id, -32602, "tools/call requires `name` (string).")

    _find = (profile.find_tool if profile is not None else find_tool)
    tool: Optional[McpTool] = _find(tool_name)
    if tool is None:
        return _err(req_id, _ERR_TOOL_NOT_FOUND, f"Unknown tool: {tool_name!r}.")

    # Scope check
    if tool.scope and not api_key.grants_scope(tool.scope):
        return _err(
            req_id,
            _ERR_SCOPE_MISSING,
            f"This API key is not scoped for {tool.scope!r} (required by tool {tool.name!r}).",
            data={"required_scope": tool.scope, "tool": tool.name},
        )

    is_sandbox = bool(getattr(api_key, "is_sandbox", False))
    cost = int(tool.cost_micro)
    is_admin = getattr(user, "role", None) == "admin"

    # Gateway self-call key: forward the caller's own key ONLY for admins (their
    # v2 self-calls are debit-exempt, so the gateway stays single-billed). This
    # lets the generic gateway work with no BRUBRU_INTERNAL_API_KEY set. Cleared
    # for non-admins so their key is never used for an internal call.
    set_gateway_caller_key(caller_key if (is_admin and caller_key) else "")

    # Billing
    if is_admin:
        # Admin users (Brubru operators) call their own MCP for free. No debit,
        # no usage event. Same policy as the REST surface in api/v1/_deps.py.
        pass
    elif is_sandbox:
        ok, reason = sandbox_consume(db, client_ip or "0.0.0.0")
        if not ok:
            return _err(
                req_id,
                _ERR_SANDBOX_CAPPED,
                "Public sandbox daily cap reached. Sign up at brubru.beresol.eu and mint your own key.",
                data={"reason_code": reason},
            )
    else:
        ok, balance_after = debit(db, api_key.user_id, cost)
        if not ok:
            return _err(
                req_id,
                _ERR_INSUFFICIENT_BALANCE,
                "Insufficient balance. Top up at brubru.beresol.eu/billing.",
                data={
                    "balance_eur_micro": balance_after,
                    "cost_eur_micro": cost,
                    "top_up_url": "https://brubru.beresol.eu/billing",
                },
            )

    # Record usage (even before handler runs, so the row exists if we need to
    # mark it refunded after a handler crash). Skipped for admin: no debit
    # happened, so no audit row either.
    usage_evt = None
    if not is_admin:
        usage_evt = record_usage(
            db,
            user_id=api_key.user_id,
            api_key_id=api_key.id,
            endpoint=f"mcp:{tool.name}",
            method="MCP",
            cost_micro=cost,
            request_id=request_id,
            status_code=None,
            is_sandbox=is_sandbox,
            # The 13 Aug 2026 incident this exists for was on THIS path: 178
            # `mcp:ask_dpp` debugging calls landed on a client's row and counted
            # as her usage. Billing is unchanged; only analytics may exclude it.
            is_probe=is_probe,
        )

    # Invoke the handler OFF the event loop. Handlers do blocking DB work (and the
    # gateway tool makes a self-HTTP call); running them on the loop would starve
    # the single worker and would DEADLOCK the gateway's self-call. Billing above
    # + refunds below stay on the loop with `db`; the handler opens its own session.
    try:
        payload = await anyio.to_thread.run_sync(invoke_tool, tool, arguments or {})
    except TypeError as exc:
        # Bad arguments — refund (caller-side error, but the work didn't ship).
        if not is_sandbox and not is_admin and usage_evt is not None:
            refund(db, api_key.user_id, cost)
            mark_event_refunded(db, usage_evt.id)
        _stamp_status(db, usage_evt, 400)
        return _err(
            req_id,
            -32602,
            f"Invalid arguments for tool {tool.name!r}: {exc}",
            data={"tool": tool.name},
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[mcp] tool {tool.name} crashed: {exc}")
        if not is_sandbox and not is_admin and usage_evt is not None:
            refund(db, api_key.user_id, cost)
            mark_event_refunded(db, usage_evt.id)
        _stamp_status(db, usage_evt, 500)
        return _err(
            req_id,
            _ERR_TOOL_HANDLER_FAILED,
            f"Tool {tool.name!r} failed. The call was refunded.",
            data={"tool": tool.name, "exception_type": type(exc).__name__},
        )

    _stamp_status(db, usage_evt, 200)
    return _ok(req_id, _tool_text_result(payload))


def _stamp_status(db, usage_evt, status_code: int) -> None:
    """Record the semantic outcome of an MCP tool call on its ledger row.

    JSON-RPC answers HTTP 200 whatever happens, and BillingRefundMiddleware
    only watches /api/v1 and /api/v2, so MCP calls would otherwise keep the NULL
    status that record_usage() writes before the handler runs. We stamp the
    JSON-RPC outcome instead of the transport status: 200 served, 400 bad
    arguments, 500 handler crash. Admin calls skip metering entirely and have no
    row to stamp.
    """
    if usage_evt is None:
        return
    try:
        set_event_status(db, usage_evt.id, status_code)
    except Exception as exc:  # noqa: BLE001 -- telemetry must never break a call
        logger.error(f"[mcp] status stamp failed for event {usage_evt.id}: {exc}")


# ---------------------------------------------------------------------------
# Single endpoint — POST /api/mcp
# ---------------------------------------------------------------------------

class JsonRpcEnvelope(BaseModel):
    """Loose envelope — JSON-RPC 2.0 leaves params/id optional/typed-loose."""
    jsonrpc: Optional[str] = None
    id: Any = None
    method: Optional[str] = None
    params: Any = None


async def _handle_mcp(
    request: Request,
    authorization: Optional[str],
    x_api_key: Optional[str],
    profile: "McpProfile",
):
    """The whole JSON-RPC lifecycle, shared by every mounted MCP server."""
    # Parse JSON body manually so we can return JSON-RPC parse errors with a
    # proper id rather than letting FastAPI's 422 surface.
    try:
        body = await request.json()
    except Exception:
        return _err(None, -32700, "Parse error: body is not valid JSON.")

    if not isinstance(body, dict):
        return _err(None, -32600, "Invalid request: expected a JSON object.")

    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}

    if not isinstance(method, str) or not method:
        return _err(req_id, -32600, "Invalid request: missing `method`.")

    # ---- Notifications never get a response ------------------------------
    if method.startswith("notifications/"):
        # MCP notifications: client just informing the server. Don't bill,
        # don't respond. FastAPI demands SOMETHING for a POST handler — return
        # 204 No Content via a small JSON ack the client can ignore.
        return {"jsonrpc": "2.0", "result": None}

    # ---- initialize is free; no auth required for the handshake ----------
    if method == "initialize":
        return _dispatch_initialize(req_id, params if isinstance(params, dict) else {}, profile)

    # ---- All other methods require auth ----------------------------------
    # Query-string fallback for hosts that only accept a URL (claude.ai web
    # custom connector, some Gemini/ChatGPT flows): ?key=... or ?api_key=...
    query_key = request.query_params.get("key") or request.query_params.get("api_key")
    plaintext = _extract_key(authorization, x_api_key, query_key)

    # No credentials at all -> emit the OAuth 2.1 discovery challenge (HTTP 401 +
    # WWW-Authenticate per the MCP Authorization spec / RFC 9728). This is what
    # makes the claude.ai connector start the OAuth flow. Clients that DO send a
    # key (?key= or header) never reach here, so Option A is untouched.
    if not plaintext:
        base = f"https://{request.headers.get('host', 'brubru-production.up.railway.app')}"
        # Point at the metadata for THIS resource, not a fixed one. Per RFC 9728
        # the client fetches the document named here and binds its token to the
        # `resource` that document declares. With a second MCP server mounted at
        # /api/mcp/dpp, a fixed challenge sent a client connecting to the DPP
        # server to metadata declaring /api/mcp: a different resource from the
        # one it was calling, so the token would carry the wrong audience.
        resource_path = request.url.path.rstrip("/") or "/api/mcp"
        return JSONResponse(
            {"jsonrpc": "2.0", "id": req_id,
             "error": {"code": _ERR_AUTH_MISSING, "message": "Authentication required."}},
            status_code=401,
            headers={"WWW-Authenticate": (
                "Bearer resource_metadata="
                f'"{base}/.well-known/oauth-protected-resource{resource_path}"'
            )},
        )

    db = SessionLocal()
    try:
        api_key, user, auth_err = _resolve_api_key(db, plaintext or "")
        if auth_err is not None:
            code, msg = auth_err
            return _err(req_id, code, msg)

        if method == "tools/list":
            return _dispatch_tools_list(req_id, profile)

        if method == "tools/call":
            client_ip = request.client.host if request.client else None
            return await _dispatch_tools_call(
                req_id,
                params if isinstance(params, dict) else {},
                db,
                api_key,
                user,
                client_ip,
                request_id=str(uuid.uuid4()),
                caller_key=plaintext,
                profile=profile,
                is_probe=is_probe_header(request.headers.get("X-Brubru-Probe")),
            )

        return _err(req_id, -32601, f"Method not found: {method!r}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tiny probe — for /mcp clients that GET the URL before POSTing.
# Common in browsers, Stripe-style health checkers, etc.
# ---------------------------------------------------------------------------

async def _handle_probe(profile: "McpProfile"):
    return {
        "service": profile.server_info["name"],
        "version": profile.server_info["version"],
        "protocol": "Model Context Protocol",
        "protocolVersion": PROTOCOL_VERSION,
        "transport": "HTTP / JSON-RPC 2.0 (POST this URL)",
        "tools_available": profile.tool_count(),
        "auth": "Authorization: Bearer <key> | X-API-Key: <key> | ?key=<key>",
        "docs": "https://brubru.beresol.eu/mcp",
    }


# ---------------------------------------------------------------------------
# Factory — mount one MCP server per profile
# ---------------------------------------------------------------------------

def make_mcp_router(*, prefix: str, profile: "McpProfile", tag: str) -> APIRouter:
    """Build an APIRouter exposing `profile` as an MCP server at `prefix`.

    Every mounted server shares _handle_mcp, so auth, billing, the JSON-RPC
    envelope and the `initialize` handshake exist once. Only the displayed name,
    the tool subset and the instructions differ.
    """
    r = APIRouter(prefix=prefix, tags=[tag])
    name = profile.server_info["name"]

    @r.post(
        "",
        include_in_schema=True,
        summary=f"{name} MCP: JSON-RPC 2.0 HTTP transport",
        description=(
            f"Model Context Protocol endpoint for {name}. Speak JSON-RPC 2.0; "
            "see /mcp on brubru.beresol.eu for client install instructions."
        ),
    )
    async def _post(  # noqa: ANN202
        request: Request,
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
        x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    ):
        return await _handle_mcp(request, authorization, x_api_key, profile)

    @r.get(
        "",
        include_in_schema=True,
        summary=f"{name} MCP probe: confirms the endpoint exists (no auth)",
    )
    async def _get():  # noqa: ANN202
        return await _handle_probe(profile)

    return r


# The original, full-surface Brubru MCP. Mounted by main.py as before.
router = make_mcp_router(prefix="/api/mcp", profile=DEFAULT_PROFILE, tag="mcp-http")


# ---------------------------------------------------------------------------
# Brubru DPP — the first per-client, on-demand MCP (Terraqui / LIFE DPP-TEX)
# ---------------------------------------------------------------------------

def _dpp_instructions(coverage: str) -> str:  # noqa: ARG001 - global coverage is wrong here
    from services.mcp.dpp_tools import DPP_TOOLS

    return (
        "Brubru DPP is a focused EU regulatory server for the Digital Product "
        "Passport. For almost any question call `ask_dpp` with the user's question: "
        "it searches the acts, the sector timetable, the registry, the harmonised "
        "standards, the battery data points and the live consultations at once.\n\n"
        "It covers: the EU acts that create passport obligations (with their FULL "
        "legal text, not summaries), when each product sector's passport becomes "
        "mandatory, how registration in the central registry works, the six "
        "harmonised EN standards, the 71 battery passport data points, textile "
        "extended producer responsibility, the ecodesign consultations including "
        "the apparel-textiles delegated act, and the Ecodesign Forum.\n\n"
        "The only hard deadline in force is 18 February 2027 for certain large "
        "batteries; textiles follow in Q3-Q4 2027 on the Commission's indicative "
        "timetable. For EU policy beyond the passport, use the main Brubru server.\n\n"
        f"{len(DPP_TOOLS)} tools. Each call is metered in euros against your Brubru "
        "API balance."
    )


def _dpp_profile() -> "McpProfile":
    from services.mcp.dpp_tools import DPP_TOOLS, find_dpp_tool, list_dpp_tools_for_mcp

    return McpProfile(
        server_info={"name": "Brubru DPP", "version": "1.0.0"},
        list_tools=list_dpp_tools_for_mcp,
        find_tool=find_dpp_tool,
        tool_count=lambda: len(DPP_TOOLS),
        instructions=_dpp_instructions,
    )


# Mounted at /api/mcp/dpp. FastAPI matches the more specific path first, so this
# does not shadow (or get shadowed by) the full-surface server at /api/mcp.
dpp_router = make_mcp_router(prefix="/api/mcp/dpp", profile=_dpp_profile(), tag="mcp-dpp")
