"""
Self-serve API Key Management (/api/me/api-keys)

Lets any authenticated Brubru user mint, list, and revoke API keys for the
Data Provider API (/api/v1/*) directly from the frontend. No admin role
required, no Professional-tier gate.

Hard caps:
    - Up to 3 active (non-revoked, non-expired) keys per user.
    - At most 10 mints per hour per user (anti-key-spam).

Plaintext is shown ONCE in the mint response and never persisted. The
frontend reveals it via a one-time-modal with copy-to-clipboard.

Routes:
    POST   /api/me/api-keys          -> mint
    GET    /api/me/api-keys          -> list (no plaintext)
    DELETE /api/me/api-keys/{key_id} -> revoke
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from api.auth import get_current_user
from core.database import get_db
from models.api_key import ApiKey, DEFAULT_SELF_SERVE_EXPIRY_DAYS
from models.user import User
from services.api_keys.scopes import (
    SCOPE_CATALOGUE,
    all_self_serve_scopes,
    validate_scope_list,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me/api-keys", tags=["self-serve-api-keys"])

# Hard caps
MAX_ACTIVE_KEYS_PER_USER = 3
MAX_MINTS_PER_HOUR = 10

# Allowed expiry windows offered in the UI dropdown
ALLOWED_EXPIRY_DAYS = (30, 90, 180, 365)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ScopeOption(BaseModel):
    """One row in the scope catalogue — drives the mint UI checkboxes."""
    name: str
    label: str
    description: str
    default_on_self_serve: bool


class CreateKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Human label, e.g. 'Production' or 'Local dev'. 3-100 characters.",
    )
    scopes: List[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="One or more read:* scopes from the catalogue. Wildcard '*' is reserved for admins.",
    )
    expires_in_days: int = Field(
        default=DEFAULT_SELF_SERVE_EXPIRY_DAYS,
        description="Lifetime in days. Must be one of 30, 90, 180, 365.",
    )


class CreateKeyResponse(BaseModel):
    """Shown ONCE to the caller. Plaintext key is never returned again."""
    id: UUID
    key: str = Field(..., description="Plaintext API key. Shown ONCE. Store securely.")
    name: str
    key_prefix: str
    scopes: List[str]
    created_at: datetime
    expires_at: Optional[datetime]
    warning: str = "Store this key securely. It will not be shown again."


class ApiKeySummary(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    scopes: List[str]
    last_used_at: Optional[datetime]
    created_at: datetime
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    is_active: bool
    is_expired: bool


class ScopeCatalogueResponse(BaseModel):
    scopes: List[ScopeOption]
    defaults: List[str]
    expiry_options_days: List[int]
    max_active_keys: int


# ---------------------------------------------------------------------------
# Catalogue (for the mint UI)
# ---------------------------------------------------------------------------

@router.get(
    "/scopes",
    response_model=ScopeCatalogueResponse,
    summary="List available scopes for self-serve key minting",
    description=(
        "Returns the scope catalogue used to populate the mint UI's checkboxes, "
        "the pre-checked default set, the allowed expiry windows, and the maximum "
        "number of active keys per user. No authentication required — this is a "
        "static catalogue."
    ),
)
async def get_scope_catalogue() -> ScopeCatalogueResponse:
    return ScopeCatalogueResponse(
        scopes=[
            ScopeOption(
                name=s.name,
                label=s.label,
                description=s.description,
                default_on_self_serve=s.default_on_self_serve,
            )
            for s in SCOPE_CATALOGUE
        ],
        defaults=all_self_serve_scopes(),
        expiry_options_days=list(ALLOWED_EXPIRY_DAYS),
        max_active_keys=MAX_ACTIVE_KEYS_PER_USER,
    )


# ---------------------------------------------------------------------------
# Mint
# ---------------------------------------------------------------------------

def _count_active_keys(db: Session, user_id: UUID) -> int:
    """Count non-revoked, non-expired keys for `user_id`."""
    now = datetime.now(timezone.utc)
    return (
        db.query(ApiKey)
        .filter(
            ApiKey.user_id == user_id,
            ApiKey.revoked_at.is_(None),
            or_(ApiKey.expires_at.is_(None), ApiKey.expires_at > now),
        )
        .count()
    )


def _count_recent_mints(db: Session, user_id: UUID) -> int:
    """Mints (including revoked ones) in the last hour. Anti-spam."""
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    return (
        db.query(ApiKey)
        .filter(ApiKey.user_id == user_id, ApiKey.created_at >= one_hour_ago)
        .count()
    )


@router.post(
    "",
    response_model=CreateKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mint a new API key for the current user",
    description=(
        "Creates a new API key with the chosen scopes and expiry. The plaintext "
        "key is returned ONCE in the response body and never again — the caller "
        "must store it. Subject to a 3-key active cap per user and a 10-mint/hour "
        "anti-spam cap."
    ),
)
async def mint_my_api_key(
    body: CreateKeyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CreateKeyResponse:
    # ---- Validate scopes ------------------------------------------------
    try:
        scopes = validate_scope_list(body.scopes, allow_wildcard=False)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": str(exc), "reason_code": "invalid_scopes"},
        )

    # ---- Validate expiry ------------------------------------------------
    if body.expires_in_days not in ALLOWED_EXPIRY_DAYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": f"expires_in_days must be one of {ALLOWED_EXPIRY_DAYS}",
                "reason_code": "invalid_expiry",
            },
        )

    # ---- 3-key cap ------------------------------------------------------
    active = _count_active_keys(db, user.id)
    if active >= MAX_ACTIVE_KEYS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": (
                    f"You have reached the maximum of {MAX_ACTIVE_KEYS_PER_USER} "
                    "active API keys. Revoke an unused key to create a new one."
                ),
                "reason_code": "key_cap_reached",
                "max_active_keys": MAX_ACTIVE_KEYS_PER_USER,
                "active_count": active,
            },
        )

    # ---- Mint-rate cap --------------------------------------------------
    recent = _count_recent_mints(db, user.id)
    if recent >= MAX_MINTS_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": (
                    f"Too many key mints in the last hour (max {MAX_MINTS_PER_HOUR}). "
                    "Try again later."
                ),
                "reason_code": "mint_rate_limited",
            },
        )

    # ---- Mint -----------------------------------------------------------
    plaintext, api_key = ApiKey.generate(
        user_id=user.id,
        name=body.name,
        scopes=scopes,
        expires_in_days=body.expires_in_days,
        is_sandbox=False,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    logger.info(
        f"[me_api_keys] minted key {api_key.id} for user {user.email} "
        f"(scopes={scopes}, expires_in_days={body.expires_in_days})"
    )

    return CreateKeyResponse(
        id=api_key.id,
        key=plaintext,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        scopes=list(api_key.scopes or []),
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
    )


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=List[ApiKeySummary],
    summary="List the current user's API keys",
    description=(
        "Returns every API key the current user has ever minted (active, revoked, "
        "and expired), most-recent first. The plaintext key is NEVER returned — "
        "only the 4-character prefix for human display."
    ),
)
async def list_my_api_keys(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[ApiKeySummary]:
    rows = (
        db.query(ApiKey)
        .filter(ApiKey.user_id == user.id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )
    return [_summary(r) for r in rows]


def _summary(r: ApiKey) -> ApiKeySummary:
    return ApiKeySummary(
        id=r.id,
        name=r.name,
        key_prefix=r.key_prefix,
        scopes=list(r.scopes or []),
        last_used_at=r.last_used_at,
        created_at=r.created_at,
        expires_at=r.expires_at,
        revoked_at=r.revoked_at,
        is_active=r.is_active,
        is_expired=r.is_expired,
    )


# ---------------------------------------------------------------------------
# Revoke
# ---------------------------------------------------------------------------

@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an API key owned by the current user",
    description=(
        "Sets revoked_at = NOW() on the key. Idempotent: revoking an already-revoked "
        "key returns 204 without changes. Returns 404 if the key does not belong to "
        "the current user."
    ),
)
async def revoke_my_api_key(
    key_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    key = (
        db.query(ApiKey)
        .filter(and_(ApiKey.id == key_id, ApiKey.user_id == user.id))
        .first()
    )
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    if key.revoked_at is not None:
        return  # idempotent — already revoked

    key.revoked_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(f"[me_api_keys] revoked key {key.id} by owner {user.email}")
    return None
