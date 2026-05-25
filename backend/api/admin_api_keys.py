"""
Admin API Key Management

Endpoints for minting, listing, and revoking Data Provider API keys.
Admin-only (for v1; self-serve UI comes later).

Routes:
    POST   /api/admin/users/{user_id}/api-keys   -> mint a key (plaintext shown once)
    GET    /api/admin/users/{user_id}/api-keys   -> list keys for a user (no plaintext)
    DELETE /api/admin/api-keys/{key_id}          -> revoke a key
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.admin_auth import get_current_admin_user
from core.database import get_db
from models.api_key import ApiKey
from models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin-api-keys"])


class MintRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Human label, e.g. 'GovClipping production'")


class MintResponse(BaseModel):
    id: UUID
    key: str = Field(..., description="Plaintext API key. Shown ONCE. Store securely.")
    name: str
    key_prefix: str
    created_at: datetime
    warning: str = "Store this key securely. It will not be shown again."


class ApiKeySummary(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    last_used_at: Optional[datetime]
    created_at: datetime
    revoked_at: Optional[datetime]
    is_active: bool


@router.post(
    "/users/{user_id}/api-keys",
    response_model=MintResponse,
    status_code=status.HTTP_201_CREATED,
)
async def mint_api_key(
    user_id: UUID,
    body: MintRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Mint a new API key for a Professional subscriber. Returns plaintext ONCE."""
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Subscription-tier gate removed 21 May 2026. API access is now gated by
    # a positive euro balance (Phase B billing middleware), not by Professional
    # tier. Admins can mint keys for any user (e.g. partners, beta testers).
    # Admin-minted keys default to scopes=["*"] and no expiry for back-compat.
    plaintext, api_key = ApiKey.generate(user_id=target.id, name=body.name)
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    logger.info(f"[admin] minted API key {api_key.id} for user {target.email} by admin {admin.email}")

    return MintResponse(
        id=api_key.id,
        key=plaintext,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        created_at=api_key.created_at,
    )


@router.get(
    "/users/{user_id}/api-keys",
    response_model=List[ApiKeySummary],
)
async def list_api_keys(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """List all API keys for a user (active and revoked). Plaintext never returned."""
    rows = (
        db.query(ApiKey)
        .filter(ApiKey.user_id == user_id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )
    return [
        ApiKeySummary(
            id=r.id,
            name=r.name,
            key_prefix=r.key_prefix,
            last_used_at=r.last_used_at,
            created_at=r.created_at,
            revoked_at=r.revoked_at,
            is_active=r.is_active,
        )
        for r in rows
    ]


@router.delete(
    "/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_api_key(
    key_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Revoke an API key (sets revoked_at = NOW())."""
    key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if key is None:
        raise HTTPException(status_code=404, detail="API key not found")
    if key.revoked_at is not None:
        return  # already revoked, idempotent
    key.revoked_at = datetime.utcnow()
    db.commit()
    logger.info(f"[admin] revoked API key {key.id} by admin {admin.email}")
