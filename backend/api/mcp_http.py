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
from typing import Any, Dict, Optional, Tuple

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
    refund,
    sandbox_consume,
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
router = APIRouter(prefix="/api/mcp", tags=["mcp-http"])

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
    return api_key, user, None


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
    """Wrap a handler return-value as an MCP `tools/call` result."""
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False, default=str),
            }
        ],
        "isError": False,
    }


# ---------------------------------------------------------------------------
# Method dispatch
# ---------------------------------------------------------------------------

def _dispatch_initialize(req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
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
            "serverInfo": SERVER_INFO,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "instructions": (
                "Brubru is EU policy intelligence for any AI assistant. For almost any "
                "question, call the single tool `ask_brubru` with the user's question — "
                "it returns the matching policy guides, the relevant EU laws (with CELEX "
                "and EUR-Lex links), and live procedure status in one call. The other "
                "tools (calendar events, EPRS, raw law/guide search) are advanced and "
                "rarely needed.\n\n"
                f"Live coverage: {coverage}.\n\n"
                "Each call is metered in euros against your Brubru API balance; mint a "
                "key and top up at https://brubru.beresol.eu/api."
            ),
        },
    )


def _dispatch_tools_list(req_id: Any) -> Dict[str, Any]:
    return _ok(req_id, {"tools": list_tools_for_mcp()})


async def _dispatch_tools_call(
    req_id: Any,
    params: Dict[str, Any],
    db: Session,
    api_key: ApiKey,
    user: User,
    client_ip: Optional[str],
    request_id: str,
    caller_key: Optional[str] = None,
) -> Dict[str, Any]:
    tool_name = params.get("name") if params else None
    arguments = params.get("arguments") if params else None
    if not isinstance(tool_name, str) or not tool_name:
        return _err(req_id, -32602, "tools/call requires `name` (string).")

    tool: Optional[McpTool] = find_tool(tool_name)
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
        return _err(
            req_id,
            _ERR_TOOL_HANDLER_FAILED,
            f"Tool {tool.name!r} failed. The call was refunded.",
            data={"tool": tool.name, "exception_type": type(exc).__name__},
        )

    return _ok(req_id, _tool_text_result(payload))


# ---------------------------------------------------------------------------
# Single endpoint — POST /api/mcp
# ---------------------------------------------------------------------------

class JsonRpcEnvelope(BaseModel):
    """Loose envelope — JSON-RPC 2.0 leaves params/id optional/typed-loose."""
    jsonrpc: Optional[str] = None
    id: Any = None
    method: Optional[str] = None
    params: Any = None


@router.post(
    "",
    include_in_schema=True,
    summary="Brubru MCP — JSON-RPC 2.0 HTTP transport",
    description=(
        "Public Model Context Protocol endpoint. Speak JSON-RPC 2.0; "
        "see /mcp on brubru.beresol.eu for client install instructions."
    ),
)
async def mcp_endpoint(
    request: Request,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
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
        return _dispatch_initialize(req_id, params if isinstance(params, dict) else {})

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
        return JSONResponse(
            {"jsonrpc": "2.0", "id": req_id,
             "error": {"code": _ERR_AUTH_MISSING, "message": "Authentication required."}},
            status_code=401,
            headers={"WWW-Authenticate": f'Bearer resource_metadata="{base}/.well-known/oauth-protected-resource"'},
        )

    db = SessionLocal()
    try:
        api_key, user, auth_err = _resolve_api_key(db, plaintext or "")
        if auth_err is not None:
            code, msg = auth_err
            return _err(req_id, code, msg)

        if method == "tools/list":
            return _dispatch_tools_list(req_id)

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
            )

        return _err(req_id, -32601, f"Method not found: {method!r}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tiny probe — for /mcp clients that GET the URL before POSTing.
# Common in browsers, Stripe-style health checkers, etc.
# ---------------------------------------------------------------------------

@router.get(
    "",
    include_in_schema=True,
    summary="MCP probe — confirms the endpoint exists (no auth)",
)
async def mcp_probe():
    return {
        "service": SERVER_INFO["name"],
        "version": SERVER_INFO["version"],
        "protocol": "Model Context Protocol",
        "protocolVersion": PROTOCOL_VERSION,
        "transport": "HTTP / JSON-RPC 2.0 (POST this URL)",
        "tools_available": len(TOOLS),
        "auth": "Authorization: Bearer <key> | X-API-Key: <key> | ?key=<key>",
        "docs": "https://brubru.beresol.eu/mcp",
    }
