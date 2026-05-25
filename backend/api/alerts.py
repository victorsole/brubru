"""Alert subscriptions API.

CRUD for `user_alert_subscriptions` + a `/run` endpoint that lets the
authenticated user trigger their own subscriptions on demand (rate-limited
to 1 per minute to avoid abusing the corpus scans). New alert events
themselves live in the `notifications` table and are served by the
existing /api/notifications endpoints.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from .auth_optional import get_current_user_dev as get_current_user

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AlertSubscriptionBase(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    query_phrase: str = Field(..., min_length=1, max_length=500)
    scopes: List[str] = Field(default_factory=lambda: ["eu_laws", "texts_adopted", "legislative_carriages", "rss_entries"])
    delivery: List[str] = Field(default_factory=lambda: ["chat_greeting", "meub_tile"])
    exclude_terms: Optional[List[str]] = None
    language_codes: Optional[List[str]] = None
    priority_override: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True


class AlertSubscriptionResponse(AlertSubscriptionBase):
    id: UUID
    user_id: UUID
    last_run_at: Optional[datetime] = None
    last_match_at: Optional[datetime] = None
    last_match_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/subscriptions", response_model=List[AlertSubscriptionResponse])
async def list_subscriptions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        text(
            """
            SELECT id, user_id, label, query_phrase, scopes, delivery,
                   exclude_terms, language_codes, priority_override,
                   notes, is_active, last_run_at, last_match_at,
                   last_match_count, created_at, updated_at
            FROM user_alert_subscriptions
            WHERE user_id = :uid
            ORDER BY created_at
            """
        ),
        {"uid": current_user.id},
    ).mappings().all()
    return [AlertSubscriptionResponse(**dict(r)) for r in rows]


@router.post(
    "/subscriptions",
    response_model=AlertSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subscription(
    payload: AlertSubscriptionBase,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.execute(
        text(
            """
            INSERT INTO user_alert_subscriptions
                (user_id, label, query_phrase, scopes, delivery, exclude_terms,
                 language_codes, priority_override, notes, is_active)
            VALUES
                (:uid, :label, :phrase, :scopes, :delivery, :exclude_terms,
                 :language_codes, :priority_override, :notes, :is_active)
            ON CONFLICT (user_id, label) DO UPDATE
                SET query_phrase = EXCLUDED.query_phrase,
                    scopes = EXCLUDED.scopes,
                    delivery = EXCLUDED.delivery,
                    exclude_terms = EXCLUDED.exclude_terms,
                    language_codes = EXCLUDED.language_codes,
                    priority_override = EXCLUDED.priority_override,
                    notes = EXCLUDED.notes,
                    is_active = EXCLUDED.is_active
            RETURNING id, user_id, label, query_phrase, scopes, delivery,
                      exclude_terms, language_codes, priority_override,
                      notes, is_active, last_run_at, last_match_at,
                      last_match_count, created_at, updated_at
            """
        ),
        {
            "uid": current_user.id,
            "label": payload.label,
            "phrase": payload.query_phrase,
            "scopes": payload.scopes,
            "delivery": payload.delivery,
            "exclude_terms": payload.exclude_terms,
            "language_codes": payload.language_codes,
            "priority_override": payload.priority_override,
            "notes": payload.notes,
            "is_active": payload.is_active,
        },
    ).mappings().first()
    db.commit()
    return AlertSubscriptionResponse(**dict(row))


@router.patch(
    "/subscriptions/{subscription_id}",
    response_model=AlertSubscriptionResponse,
)
async def update_subscription(
    subscription_id: UUID,
    payload: AlertSubscriptionBase,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.execute(
        text(
            """
            UPDATE user_alert_subscriptions
            SET label = :label,
                query_phrase = :phrase,
                scopes = :scopes,
                delivery = :delivery,
                exclude_terms = :exclude_terms,
                language_codes = :language_codes,
                priority_override = :priority_override,
                notes = :notes,
                is_active = :is_active
            WHERE id = :sid AND user_id = :uid
            RETURNING id, user_id, label, query_phrase, scopes, delivery,
                      exclude_terms, language_codes, priority_override,
                      notes, is_active, last_run_at, last_match_at,
                      last_match_count, created_at, updated_at
            """
        ),
        {
            "sid": subscription_id,
            "uid": current_user.id,
            "label": payload.label,
            "phrase": payload.query_phrase,
            "scopes": payload.scopes,
            "delivery": payload.delivery,
            "exclude_terms": payload.exclude_terms,
            "language_codes": payload.language_codes,
            "priority_override": payload.priority_override,
            "notes": payload.notes,
            "is_active": payload.is_active,
        },
    ).mappings().first()
    if not row:
        raise HTTPException(404, "Subscription not found")
    db.commit()
    return AlertSubscriptionResponse(**dict(row))


@router.delete(
    "/subscriptions/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_subscription(
    subscription_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    res = db.execute(
        text("DELETE FROM user_alert_subscriptions WHERE id = :sid AND user_id = :uid"),
        {"sid": subscription_id, "uid": current_user.id},
    )
    db.commit()
    if res.rowcount == 0:
        raise HTTPException(404, "Subscription not found")
    return None


@router.post("/run-now")
async def run_now(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run all of the current user's active subscriptions immediately.

    Rate-limited: refuses if last_run_at was within the last 60 seconds for
    any of the user's subs.
    """
    # Throttle check
    too_recent = db.execute(
        text(
            """
            SELECT count(*) AS n
            FROM user_alert_subscriptions
            WHERE user_id = :uid
              AND is_active = TRUE
              AND last_run_at > NOW() - INTERVAL '60 seconds'
            """
        ),
        {"uid": current_user.id},
    ).scalar()
    if too_recent and too_recent > 0:
        raise HTTPException(429, "Alerts were run within the last 60 seconds. Try again shortly.")
    # Defer the import so route load stays cheap.
    from services.alerts.saved_search_runner import run_all
    summary = run_all(user_email=current_user.email, dry_run=False)
    return summary
