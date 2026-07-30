"""
Brubru MCP — OAuth 2.1 Authorization Server (Option B, 30 July 2026).

Lets MCP hosts (claude.ai web/Desktop connector, ChatGPT, Gemini, DeepSeek) connect
via OAuth instead of a key-in-URL. Implements the MCP Authorization spec (OAuth 2.1
+ PKCE + dynamic client registration + RFC 8414/9728 discovery).

Design — lean, migration-free:
    - Dynamic Client Registration is OPEN and stateless: any client may register and
      gets a random client_id back. Security comes from PKCE + the user login at
      /authorize, and from binding redirect_uri into the (signed) authorization code.
    - The authorization CODE and the access/refresh TOKENS are signed JWTs (reusing
      Brubru's SECRET_KEY), so there is NO new database table.
    - Single-use codes are enforced by an in-process used-jti set (prod is a single
      worker; codes live 60s anyway).
    - On consent we find-or-create ONE "MCP OAuth" ApiKey per user and embed its id
      in the tokens, so the MCP request path's existing scope + euro-billing logic is
      reused unchanged. Admins stay billing-exempt exactly as with a normal key.

Coexistence: this does NOT change the ?key= / Authorization-header paths. The MCP
endpoint (api/mcp_http.py) accepts a Bearer that is either a brubru_live_ key OR an
OAuth access-token JWT minted here.

Flow: 401 challenge (mcp_http) -> discover (well-known) -> register -> authorize
(login+consent) -> token -> Bearer access token on /api/mcp.
"""

from __future__ import annotations

import base64
import hashlib
import html
import logging
import secrets
import time
import uuid
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jose import JWTError, jwt

from api.auth import ALGORITHM, SECRET_KEY, verify_password
from core.database import SessionLocal
from models.api_key import ApiKey
from models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mcp-oauth"])

# JWT `typ` markers so a code can never be replayed as a token, etc.
_TYP_CODE = "brubru_mcp_code"
_TYP_ACCESS = "brubru_mcp_at"
_TYP_REFRESH = "brubru_mcp_rt"

CODE_TTL = 60                       # seconds — auth code is short-lived
ACCESS_TTL = 60 * 60               # 1 hour
REFRESH_TTL = 60 * 60 * 24 * 30    # 30 days
SCOPE = "mcp"

# Single-use enforcement for authorization codes (in-process; single worker).
_USED_CODE_JTI: set[str] = set()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_url(request: Request) -> str:
    """Public origin, forced https. Must match what the host discovered."""
    host = request.headers.get("host") or request.url.netloc
    return f"https://{host}"


def _sign(claims: Dict[str, Any], ttl: int, typ: str) -> str:
    now = int(time.time())
    payload = {**claims, "typ": typ, "iat": now, "exp": now + ttl, "jti": uuid.uuid4().hex}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _verify(token: str, typ: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if payload.get("typ") != typ:
        return None
    return payload


def _pkce_ok(verifier: str, challenge: str) -> bool:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    computed = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return secrets.compare_digest(computed, challenge)


def _oauth_api_key_id(db, user_id: uuid.UUID) -> str:
    """Find-or-create the per-user 'MCP OAuth' ApiKey; return its id (str)."""
    existing = (
        db.query(ApiKey)
        .filter(ApiKey.user_id == user_id, ApiKey.name == "MCP OAuth", ApiKey.revoked_at.is_(None))
        .first()
    )
    if existing is not None:
        return str(existing.id)
    _plaintext, inst = ApiKey.generate(user_id, "MCP OAuth", scopes=["*"], expires_in_days=None)
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return str(inst.id)


def resolve_oauth_access_token(db, token: str):
    """Used by mcp_http.py: map an OAuth access-token JWT -> (ApiKey, User) or None."""
    payload = _verify(token, _TYP_ACCESS)
    if payload is None:
        return None, None
    akid = payload.get("akid")
    if not akid:
        return None, None
    api_key = db.query(ApiKey).filter(ApiKey.id == akid, ApiKey.revoked_at.is_(None)).first()
    if api_key is None or api_key.is_expired:
        return None, None
    user = db.query(User).filter(User.id == api_key.user_id).first()
    if user is None or not user.is_active:
        return None, None
    return api_key, user


# ---------------------------------------------------------------------------
# Discovery — RFC 9728 (protected resource) + RFC 8414 (authorization server)
# claude.ai probes both the bare path and the /api/mcp-suffixed path.
# ---------------------------------------------------------------------------

def _protected_resource_metadata(request: Request) -> dict:
    base = _base_url(request)
    return {
        "resource": f"{base}/api/mcp",
        "authorization_servers": [base],
        "scopes_supported": [SCOPE],
        "bearer_methods_supported": ["header"],
        "resource_documentation": "https://brubru.beresol.eu/mcp",
    }


def _authorization_server_metadata(request: Request) -> dict:
    base = _base_url(request)
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": [SCOPE],
    }


@router.get("/.well-known/oauth-protected-resource", include_in_schema=False)
@router.get("/.well-known/oauth-protected-resource/api/mcp", include_in_schema=False)
async def protected_resource_metadata(request: Request):
    return JSONResponse(_protected_resource_metadata(request))


@router.get("/.well-known/oauth-authorization-server", include_in_schema=False)
@router.get("/.well-known/oauth-authorization-server/api/mcp", include_in_schema=False)
async def authorization_server_metadata(request: Request):
    return JSONResponse(_authorization_server_metadata(request))


# ---------------------------------------------------------------------------
# Dynamic Client Registration — RFC 7591 (open, stateless)
# ---------------------------------------------------------------------------

@router.post("/oauth/register", include_in_schema=False)
async def register_client(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    redirect_uris = body.get("redirect_uris") or []
    client_id = "mcp-" + secrets.token_urlsafe(18)
    return JSONResponse(
        {
            "client_id": client_id,
            "client_id_issued_at": int(time.time()),
            "client_name": body.get("client_name", "MCP Client"),
            "redirect_uris": redirect_uris,
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "scope": SCOPE,
        },
        status_code=201,
    )


# ---------------------------------------------------------------------------
# Authorize — login + consent, then issue a PKCE-bound authorization code
# ---------------------------------------------------------------------------

def _login_page(params: Dict[str, str], error: str = "") -> str:
    hidden = "\n".join(
        f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(v)}">'
        for k, v in params.items() if v is not None
    )
    err_html = f'<p class="err">{html.escape(error)}</p>' if error else ""
    client = html.escape(params.get("client_id", "an application"))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in to Brubru</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; background:#f6f7fb;
         display:flex; min-height:100vh; align-items:center; justify-content:center; margin:0; }}
  .card {{ background:#fff; max-width:380px; width:92%; padding:2rem 1.8rem; border-radius:14px;
          box-shadow:0 10px 40px rgba(20,20,60,.12); }}
  h1 {{ font-size:1.25rem; margin:.2rem 0 .3rem; }}
  p.sub {{ color:#555; font-size:.9rem; margin:0 0 1.3rem; }}
  label {{ display:block; font-size:.8rem; color:#333; margin:.7rem 0 .25rem; }}
  input[type=email], input[type=password] {{ width:100%; padding:.6rem .7rem; border:1px solid #ccd;
          border-radius:8px; font-size:.95rem; box-sizing:border-box; }}
  button {{ width:100%; margin-top:1.3rem; padding:.7rem; border:0; border-radius:8px;
           background:linear-gradient(135deg,#3b5bdb,#7b4fe0); color:#fff; font-size:.95rem;
           font-weight:600; cursor:pointer; }}
  .err {{ color:#c0342b; font-size:.82rem; margin:.6rem 0 0; }}
  .grant {{ font-size:.78rem; color:#666; margin-top:1.1rem; text-align:center; }}
</style></head><body>
  <form class="card" method="post" action="/oauth/authorize">
    <h1>Sign in to Brubru</h1>
    <p class="sub">Authorise <strong>{client}</strong> to access Brubru's EU policy tools on your behalf.</p>
    {err_html}
    <label>Email</label>
    <input type="email" name="email" autocomplete="username" required autofocus>
    <label>Password</label>
    <input type="password" name="password" autocomplete="current-password" required>
    {hidden}
    <button type="submit">Sign in &amp; authorise</button>
    <p class="grant">You are granting read access to EU legislation, procedures, calendar and knowledge guides.</p>
  </form>
</body></html>"""


_OAUTH_PARAMS = ("response_type", "client_id", "redirect_uri", "code_challenge",
                 "code_challenge_method", "state", "scope", "resource")


@router.get("/oauth/authorize", include_in_schema=False)
async def authorize_get(request: Request):
    q = request.query_params
    params = {k: q.get(k) for k in _OAUTH_PARAMS}
    # Minimal validation up front (better errors than after a login).
    if q.get("response_type") != "code":
        return JSONResponse({"error": "unsupported_response_type"}, status_code=400)
    if not q.get("code_challenge") or q.get("code_challenge_method", "S256") != "S256":
        return JSONResponse({"error": "invalid_request", "error_description": "PKCE S256 required"}, status_code=400)
    if not q.get("redirect_uri"):
        return JSONResponse({"error": "invalid_request", "error_description": "redirect_uri required"}, status_code=400)
    return HTMLResponse(_login_page(params))


@router.post("/oauth/authorize", include_in_schema=False)
async def authorize_post(request: Request):
    form = await request.form()
    params = {k: (form.get(k) or "") for k in _OAUTH_PARAMS}
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""
    redirect_uri = params["redirect_uri"]

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None or not user.password_hash or not verify_password(password, user.password_hash):
            return HTMLResponse(_login_page(params, "Incorrect email or password."), status_code=401)
        if not user.is_active:
            return HTMLResponse(_login_page(params, "This account is inactive."), status_code=403)

        akid = _oauth_api_key_id(db, user.id)
        code = _sign(
            {
                "sub": str(user.id),
                "akid": akid,
                "cid": params["client_id"],
                "ru": redirect_uri,
                "rc": params["code_challenge"],
            },
            CODE_TTL,
            _TYP_CODE,
        )
    finally:
        db.close()

    sep = "&" if "?" in redirect_uri else "?"
    qs = urlencode({"code": code, **({"state": params["state"]} if params["state"] else {})})
    return RedirectResponse(f"{redirect_uri}{sep}{qs}", status_code=302)


# ---------------------------------------------------------------------------
# Token — authorization_code (PKCE) + refresh_token
# ---------------------------------------------------------------------------

def _token_error(err: str, desc: str = "", code: int = 400) -> JSONResponse:
    body = {"error": err}
    if desc:
        body["error_description"] = desc
    return JSONResponse(body, status_code=code)


def _issue_tokens(sub: str, akid: str) -> dict:
    access = _sign({"sub": sub, "akid": akid, "scope": SCOPE}, ACCESS_TTL, _TYP_ACCESS)
    refresh = _sign({"sub": sub, "akid": akid}, REFRESH_TTL, _TYP_REFRESH)
    return {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": ACCESS_TTL,
        "refresh_token": refresh,
        "scope": SCOPE,
    }


@router.post("/oauth/token", include_in_schema=False)
async def token(request: Request):
    form = await request.form()
    grant_type = form.get("grant_type")

    if grant_type == "authorization_code":
        code = form.get("code") or ""
        verifier = form.get("code_verifier") or ""
        redirect_uri = form.get("redirect_uri") or ""
        payload = _verify(code, _TYP_CODE)
        if payload is None:
            return _token_error("invalid_grant", "code invalid or expired")
        jti = payload.get("jti")
        if jti in _USED_CODE_JTI:
            return _token_error("invalid_grant", "code already used")
        if not verifier or not _pkce_ok(verifier, payload.get("rc", "")):
            return _token_error("invalid_grant", "PKCE verification failed")
        if redirect_uri and redirect_uri != payload.get("ru"):
            return _token_error("invalid_grant", "redirect_uri mismatch")
        _USED_CODE_JTI.add(jti)
        return JSONResponse(_issue_tokens(payload["sub"], payload["akid"]))

    if grant_type == "refresh_token":
        payload = _verify(form.get("refresh_token") or "", _TYP_REFRESH)
        if payload is None:
            return _token_error("invalid_grant", "refresh token invalid or expired")
        return JSONResponse(_issue_tokens(payload["sub"], payload["akid"]))

    return _token_error("unsupported_grant_type", f"grant_type={grant_type!r}")
