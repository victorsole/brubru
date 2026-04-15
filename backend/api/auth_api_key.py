"""
API Key Authentication

FastAPI dependency for authenticating Data Provider API requests via the
X-API-Key header. Used on /api/v1/* endpoints (public, paid).

Flow:
    1. Extract X-API-Key header (missing -> 401)
    2. Check prefix "brubru_live_" (wrong format -> 401)
    3. SHA-256 the plaintext, look up active api_keys row (not found -> 401)
    4. Load the owning user (not found or inactive -> 401)
    5. Gate: user.subscription_tier must be "blue" (otherwise -> 403)
    6. Attach ApiKey + User to request.state for downstream use (rate limiter)
    7. Schedule a background task to update last_used_at + last_used_ip
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status, BackgroundTasks
from sqlalchemy.orm import Session

from core.database import get_db, SessionLocal
from models.api_key import ApiKey, KEY_PREFIX
from models.user import User

logger = logging.getLogger(__name__)


REQUIRED_TIER = "blue"


def _update_last_used(api_key_id, ip: Optional[str]) -> None:
    """Fire-and-forget background update of last_used_at / last_used_ip."""
    try:
        db = SessionLocal()
        try:
            key = db.query(ApiKey).filter(ApiKey.id == api_key_id).first()
            if key is None:
                return
            key.last_used_at = datetime.utcnow()
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
    db: Session = Depends(get_db),
) -> User:
    """Authenticate an /api/v1/* caller by API key."""

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not x_api_key.startswith(KEY_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
        )

    key_hash = ApiKey.hash_plaintext(x_api_key)
    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
        .first()
    )
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    user = db.query(User).filter(User.id == api_key.user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key owner is inactive",
        )

    if user.subscription_tier != REQUIRED_TIER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API access requires the Professional subscription",
        )

    # Attach for downstream dependencies (e.g. per-key rate limiter)
    request.state.api_key = api_key
    request.state.api_user = user

    client_ip = request.client.host if request.client else None
    background_tasks.add_task(_update_last_used, api_key.id, client_ip)

    return user
