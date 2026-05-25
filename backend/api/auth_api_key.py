"""
API Key Authentication

FastAPI dependency for authenticating Data Provider API requests via either
`X-API-Key` or `Authorization: Bearer` header. Used on /api/v1/* endpoints.

Flow:
    1. Extract the key from whichever header is present (Bearer wins).
    2. Check prefix "brubru_live_" (wrong format -> 401).
    3. SHA-256 the plaintext, look up active row (not found -> 401).
    4. Check expiry (expires_at set and in the past -> 401 key_expired).
    5. Load the owning user (not found or inactive -> 401).
    6. Attach ApiKey + User to request.state for downstream dependencies
       (scope check in api.v1._deps; billing middleware in Phase B).
    7. Schedule a background task to update last_used_at + last_used_ip.

What changed in Phase A (21 May 2026):
    - The `subscription_tier == "blue"` gate is REMOVED. API access is now
      open to any user with a valid key; commercial access is gated by a
      positive euro balance (Phase B billing middleware), not by subscription.
    - `expires_at` is checked. Self-serve mints default to 180-day lifetime;
      admin mints default to NULL (never expires) for back-compat.
    - `is_sandbox` keys are recognised — they bypass the user-balance debit
      (handled in Phase B) and bill against the shared sandbox pool instead.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from core.database import SessionLocal, get_db
from models.api_key import ApiKey, KEY_PREFIX
from models.user import User

logger = logging.getLogger(__name__)


def _update_last_used(api_key_id, ip: Optional[str]) -> None:
    """Fire-and-forget background update of last_used_at / last_used_ip."""
    try:
        db = SessionLocal()
        try:
            key = db.query(ApiKey).filter(ApiKey.id == api_key_id).first()
            if key is None:
                return
            key.last_used_at = datetime.now(timezone.utc)
            if ip:
                key.last_used_ip = ip
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.warning(f"[api_key] failed to update last_used: {exc}")


async def get_api_user(
    request: Request,
    background_tasks: BackgroundTasks,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate an /api/v1/* caller by API key.

    Accepts either `X-API-Key: brubru_live_...` or
    `Authorization: Bearer brubru_live_...`. Bearer wins if both are set.
    """

    # ---- 1. Extract -----------------------------------------------------
    extracted: Optional[str] = None
    if authorization:
        parts = authorization.strip().split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            extracted = parts[1].strip()
    if not extracted and x_api_key:
        extracted = x_api_key.strip()

    if not extracted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Unauthorized: Missing API key",
                "reason_code": "auth_missing_key",
            },
            headers={"WWW-Authenticate": 'Bearer realm="Brubru API"'},
        )

    # ---- 2. Format ------------------------------------------------------
    if not extracted.startswith(KEY_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Unauthorized: Invalid API key format",
                "reason_code": "auth_invalid_format",
            },
        )

    # ---- 3. Lookup ------------------------------------------------------
    key_hash = ApiKey.hash_plaintext(extracted)
    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
        .first()
    )
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Unauthorized: API key not found or revoked",
                "reason_code": "auth_key_not_found",
            },
        )

    # ---- 4. Expiry ------------------------------------------------------
    if api_key.is_expired:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Unauthorized: API key has expired",
                "reason_code": "key_expired",
            },
        )

    # ---- 5. Owner -------------------------------------------------------
    user = db.query(User).filter(User.id == api_key.user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Unauthorized: API key owner is inactive",
                "reason_code": "org_inactive",
            },
        )

    # NOTE: subscription_tier check intentionally removed (21 May 2026).
    # Commercial access is gated by a positive euro balance (Phase B), not
    # by subscription tier. Anyone with a valid key may authenticate.

    # ---- 6. Attach + 7. Background -------------------------------------
    request.state.api_key = api_key
    request.state.api_user = user
    request.state.api_key_is_sandbox = bool(api_key.is_sandbox)

    client_ip = request.client.host if request.client else None
    background_tasks.add_task(_update_last_used, api_key.id, client_ip)

    return user
