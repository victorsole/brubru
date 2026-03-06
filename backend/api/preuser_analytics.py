"""
Pre-User Analytics API

Endpoints for tracking pre-user funnel events and A/B test reporting.

- POST /api/analytics/preuser-event  (unauthenticated, rate-limited)
- GET  /api/admin/analytics/preuser-funnel  (admin only)
"""

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from core.database import get_db
from models.pre_user_event import PreUserEvent, VALID_EVENT_TYPES
from api.admin_auth import get_current_admin_user

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------- In-memory rate limiter (20 events/min/pre_user_id) ----------

_rate_buckets: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 20
RATE_WINDOW = 60  # seconds


def _is_rate_limited(pre_user_id: str) -> bool:
    now = time.time()
    bucket = _rate_buckets[pre_user_id]
    # Evict old entries
    _rate_buckets[pre_user_id] = [ts for ts in bucket if now - ts < RATE_WINDOW]
    if len(_rate_buckets[pre_user_id]) >= RATE_LIMIT:
        return True
    _rate_buckets[pre_user_id].append(now)
    return False


def _compute_variant(pre_user_id: str) -> str:
    """Deterministic A/B variant from last hex digit of UUID."""
    try:
        return "B" if int(pre_user_id[-1], 16) % 2 == 1 else "A"
    except (ValueError, IndexError):
        return "A"


# ---------- POST: fire-and-forget event ingestion ----------

class PreUserEventRequest(BaseModel):
    pre_user_id: str = Field(..., min_length=1, max_length=36)
    event_type: str = Field(..., min_length=1, max_length=30)
    event_metadata: Optional[dict] = None


@router.post("/api/analytics/preuser-event", status_code=204)
async def track_preuser_event(
    request: PreUserEventRequest,
    db: Session = Depends(get_db),
):
    """Record a pre-user funnel event. Unauthenticated, rate-limited."""
    if request.event_type not in VALID_EVENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid event_type: {request.event_type}")

    if _is_rate_limited(request.pre_user_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    variant = _compute_variant(request.pre_user_id)

    try:
        event = PreUserEvent(
            pre_user_id=request.pre_user_id,
            event_type=request.event_type,
            ab_variant=variant,
            event_metadata=request.event_metadata,
        )
        db.add(event)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"[WARN] Failed to save pre-user event (non-fatal): {e}")
        # Analytics never blocks UX -- swallow the error
        return

    return None  # 204 No Content


# ---------- POST: pre-user email capture ----------

class PreUserEmailRequest(BaseModel):
    pre_user_id: str = Field(..., min_length=1, max_length=36)
    email: str = Field(..., min_length=3, max_length=254)


@router.post("/api/analytics/preuser-email", status_code=204)
async def capture_preuser_email(
    request: PreUserEmailRequest,
    db: Session = Depends(get_db),
):
    """Capture a pre-user email for daily brief subscription. Unauthenticated."""
    if _is_rate_limited(request.pre_user_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    variant = _compute_variant(request.pre_user_id)

    try:
        event = PreUserEvent(
            pre_user_id=request.pre_user_id,
            event_type="email_captured",
            ab_variant=variant,
            event_metadata={"email": request.email},
        )
        db.add(event)
        db.commit()
        logger.info(f"[OK] Pre-user email captured: {request.email[:3]}***")

        # Send welcome email with today's brief (fire-and-forget)
        try:
            from services.daily_brief_email import send_welcome_brief
            send_welcome_brief(request.email, db)
        except Exception as e:
            logger.warning(f"[WARN] Welcome email failed (non-fatal): {e}")

    except Exception as e:
        db.rollback()
        logger.warning(f"[WARN] Failed to save pre-user email (non-fatal): {e}")

    return None  # 204 No Content


# ---------- GET: admin funnel report ----------

@router.get("/api/admin/analytics/preuser-funnel")
async def preuser_funnel_report(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin_user),
):
    """Return per-variant funnel metrics for the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Unique users per variant per event type
    rows = (
        db.query(
            PreUserEvent.ab_variant,
            PreUserEvent.event_type,
            func.count(PreUserEvent.id).label("total_events"),
            func.count(func.distinct(PreUserEvent.pre_user_id)).label("unique_users"),
        )
        .filter(PreUserEvent.created_at >= since)
        .group_by(PreUserEvent.ab_variant, PreUserEvent.event_type)
        .all()
    )

    # Build structured result
    funnel: dict = {"A": {}, "B": {}}
    for variant, event_type, total, unique in rows:
        funnel[variant][event_type] = {"total_events": total, "unique_users": unique}

    # Compute derived rates
    def _rate(variant: str, numerator_event: str, denominator_event: str) -> Optional[float]:
        denom = funnel[variant].get(denominator_event, {}).get("unique_users", 0)
        if denom == 0:
            return None
        numer = funnel[variant].get(numerator_event, {}).get("unique_users", 0)
        return round(numer / denom, 4)

    result = {
        "period_days": days,
        "since": since.isoformat(),
        "variants": {},
    }

    for v in ("A", "B"):
        result["variants"][v] = {
            "events": funnel[v],
            "second_query_rate": _rate(v, "query_2", "query_1"),
            "third_query_rate": _rate(v, "query_3", "query_1"),
            "signup_rate": _rate(v, "signed_up", "query_1"),
        }

    return result
