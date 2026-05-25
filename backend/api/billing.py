"""
API Billing endpoints (/api/billing/*) — Phase B (21 May 2026).

Routes:
    POST /api/billing/topup     -> create a Stripe PaymentIntent, return client_secret
    POST /api/billing/webhook   -> Stripe webhook handler (payment_intent.succeeded)
    GET  /api/billing/balance   -> current balance + recent usage + recent top-ups
    POST /api/billing/auto-topup -> toggle + threshold + amount

All amounts are EUR euros at the API surface; converted to micro-euros (BIGINT)
internally to avoid float drift.

This service does NOT replace the consumer-app subscription flow at /stripe/*.
It runs in parallel: subscription pays for the chat app; API credits pay for
the data API.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from api.auth import get_current_user
from core.config import settings
from core.database import get_db
from models.api_billing import ApiTopupEvent, ApiUsageEvent
from models.user import User
from services.billing.api_meter import credit_topup

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["api-billing"])

# Stripe is configured at the module level in api/stripe_payment.py; we reuse
# that key here defensively.
stripe.api_key = settings.STRIPE_SECRET_KEY

MICRO_PER_EUR = 1_000_000
MIN_TOPUP_EUR_MICRO = 1_000_000   # 1 EUR
MAX_TOPUP_EUR_MICRO = 5_000_000_000  # 5,000 EUR sanity ceiling


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TopupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount_eur: float = Field(..., gt=0, le=5000, description="Amount in EUR. Minimum 1.")


class TopupResponse(BaseModel):
    session_id: str
    checkout_url: str
    amount_eur: float


class AutoTopupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    threshold_eur: Optional[float] = Field(default=None, ge=0, le=5000)
    amount_eur: Optional[float] = Field(default=None, ge=1, le=5000)


class AutoTopupResponse(BaseModel):
    enabled: bool
    threshold_eur: Optional[float]
    amount_eur: Optional[float]


class UsageRow(BaseModel):
    id: int
    endpoint: str
    method: str
    cost_eur: float
    status_code: Optional[int]
    refunded: bool
    is_sandbox: bool
    created_at: datetime


class TopupRow(BaseModel):
    id: UUID
    amount_eur: float
    status: str
    created_at: datetime
    succeeded_at: Optional[datetime]


class BalanceResponse(BaseModel):
    balance_eur: float
    balance_eur_micro: int
    auto_topup: AutoTopupResponse
    recent_usage: List[UsageRow]
    recent_topups: List[TopupRow]


# ---------------------------------------------------------------------------
# Top-up
# ---------------------------------------------------------------------------

@router.post(
    "/topup",
    response_model=TopupResponse,
    summary="Create a Stripe PaymentIntent to top up the API balance",
    description=(
        "Creates a Stripe PaymentIntent for the requested amount (minimum 1 EUR). "
        "Returns the `client_secret` for Stripe Elements / the Payment Sheet, plus "
        "the Stripe publishable key. The balance is credited only once the webhook "
        "for `payment_intent.succeeded` fires."
    ),
)
async def create_topup(
    body: TopupRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TopupResponse:
    amount_micro = int(round(body.amount_eur * MICRO_PER_EUR))
    if amount_micro < MIN_TOPUP_EUR_MICRO:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "Minimum top-up is 1 EUR.",
                "reason_code": "topup_below_minimum",
                "minimum_eur": 1.0,
            },
        )
    if amount_micro > MAX_TOPUP_EUR_MICRO:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "Top-ups above 5,000 EUR must be invoiced — contact hello@beresol.eu.",
                "reason_code": "topup_above_maximum",
            },
        )

    # Construct the success / cancel URLs from the request origin so they
    # work on both localhost and brubru.beresol.eu.
    origin = settings.FRONTEND_URL if hasattr(settings, "FRONTEND_URL") else "https://brubru.beresol.eu"
    success_url = f"{origin}/billing?topup=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/billing?topup=cancelled"

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {
                        "name": "Brubru API credits",
                        "description": f"{body.amount_eur:.2f} EUR of credits for the Brubru Data API",
                    },
                    "unit_amount": int(round(body.amount_eur * 100)),  # cents
                },
                "quantity": 1,
            }],
            customer_email=user.email,
            metadata={
                "brubru_user_id": str(user.id),
                "brubru_product": "api_credits",
                "brubru_amount_micro": str(amount_micro),
            },
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        logger.error(f"[billing] Stripe error creating checkout session: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "Could not create checkout session", "reason_code": "stripe_error"},
        )

    # Record as pending. The webhook will flip status to succeeded once Stripe
    # confirms the underlying PaymentIntent. We store session.id as the stable
    # reference; payment_intent is filled in by the webhook handler.
    evt = ApiTopupEvent(
        user_id=user.id,
        amount_eur_micro=amount_micro,
        stripe_payment_intent_id=session.id,  # session.id (cs_*) is unique + stable
        status="pending",
    )
    db.add(evt)
    db.commit()

    return TopupResponse(
        session_id=session.id,
        checkout_url=session.url,
        amount_eur=body.amount_eur,
    )


# ---------------------------------------------------------------------------
# Stripe webhook
# ---------------------------------------------------------------------------

@router.post(
    "/webhook",
    summary="Stripe webhook handler — credits the balance on payment success",
    description=(
        "Receives Stripe webhooks. On `payment_intent.succeeded` for an API-credits "
        "PaymentIntent, atomically credits the user's balance and marks the topup "
        "event as succeeded. Idempotent — Stripe retries are safe."
    ),
    include_in_schema=False,  # webhook isn't a public-facing endpoint
)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    # Phase B uses a SEPARATE webhook secret from the subscriptions flow because
    # Stripe generates a unique signing secret per webhook endpoint. Falls back
    # to STRIPE_WEBHOOK_SECRET for backward-compat in single-endpoint dev setups.
    webhook_secret = settings.STRIPE_BILLING_WEBHOOK_SECRET or settings.STRIPE_WEBHOOK_SECRET

    if not webhook_secret:
        # Dev only — log and skip verification. Production MUST set the secret.
        logger.warning(
            "[billing] STRIPE_BILLING_WEBHOOK_SECRET not set; skipping signature "
            "verification. Set this in Railway before going live."
        )
        try:
            event = stripe.Event.construct_from(__import__("json").loads(payload), stripe.api_key)
        except Exception as exc:
            logger.error(f"[billing] bad webhook payload: {exc}")
            raise HTTPException(status_code=400, detail="invalid payload")
    else:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except (ValueError, stripe.error.SignatureVerificationError) as exc:  # type: ignore[attr-defined]
            logger.error(f"[billing] webhook signature invalid: {exc}")
            raise HTTPException(status_code=400, detail="invalid signature")

    if event.type == "checkout.session.completed":
        session_obj = event.data.object
        product = (session_obj.get("metadata") or {}).get("brubru_product")
        if product != "api_credits":
            return {"received": True, "ignored": "not_api_credits"}
        # Only credit if the payment actually succeeded (mode=payment + paid).
        if session_obj.get("payment_status") == "paid":
            await _apply_successful_topup(db, session_obj.id)

    elif event.type in ("checkout.session.expired", "checkout.session.async_payment_failed"):
        session_obj = event.data.object
        product = (session_obj.get("metadata") or {}).get("brubru_product")
        if product == "api_credits":
            db.query(ApiTopupEvent).filter(
                ApiTopupEvent.stripe_payment_intent_id == session_obj.id
            ).update({"status": "failed", "failed_at": datetime.now(timezone.utc)})
            db.commit()

    return {"received": True}


async def _apply_successful_topup(db: Session, session_id: str) -> None:
    """Credit the user balance + flip topup_event status. Idempotent — Stripe
    retries are safe.
    """
    evt = (
        db.query(ApiTopupEvent)
        .filter(ApiTopupEvent.stripe_payment_intent_id == session_id)
        .first()
    )
    if evt is None:
        logger.warning(f"[billing] no topup event for session {session_id}; skipping")
        return
    if evt.status == "succeeded":
        return  # idempotent — Stripe retried
    credit_topup(db, evt.user_id, int(evt.amount_eur_micro))
    evt.status = "succeeded"
    evt.succeeded_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(
        f"[billing] credited {evt.amount_eur_micro} μEUR to {evt.user_id} (session {session_id})"
    )


# ---------------------------------------------------------------------------
# Balance + history
# ---------------------------------------------------------------------------

def _u_to_e(u: int) -> float:
    return round(int(u) / MICRO_PER_EUR, 6)


@router.get(
    "/balance",
    response_model=BalanceResponse,
    summary="Current API balance + recent usage + recent top-ups",
    description=(
        "Returns the caller's current balance (EUR and μEUR), the auto-top-up "
        "settings, the 50 most recent usage events, and the 10 most recent "
        "top-ups. Useful as the data source for the /api/billing dashboard."
    ),
)
async def get_balance(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BalanceResponse:
    # Re-fetch for fresh balance (other requests may have debited).
    fresh = db.query(User).filter(User.id == user.id).first()
    if fresh is None:
        raise HTTPException(status_code=404, detail="user not found")

    usage_rows = (
        db.query(ApiUsageEvent)
        .filter(ApiUsageEvent.user_id == fresh.id)
        .order_by(desc(ApiUsageEvent.created_at))
        .limit(50)
        .all()
    )
    topup_rows = (
        db.query(ApiTopupEvent)
        .filter(ApiTopupEvent.user_id == fresh.id)
        .order_by(desc(ApiTopupEvent.created_at))
        .limit(10)
        .all()
    )

    return BalanceResponse(
        balance_eur=_u_to_e(fresh.api_balance_eur_micro or 0),
        balance_eur_micro=int(fresh.api_balance_eur_micro or 0),
        auto_topup=AutoTopupResponse(
            enabled=bool(fresh.api_auto_topup_enabled),
            threshold_eur=_u_to_e(fresh.api_auto_topup_threshold_micro) if fresh.api_auto_topup_threshold_micro else None,
            amount_eur=_u_to_e(fresh.api_auto_topup_amount_micro) if fresh.api_auto_topup_amount_micro else None,
        ),
        recent_usage=[
            UsageRow(
                id=r.id,
                endpoint=r.endpoint,
                method=r.method,
                cost_eur=_u_to_e(r.cost_eur_micro),
                status_code=r.status_code,
                refunded=bool(r.refunded),
                is_sandbox=bool(r.is_sandbox),
                created_at=r.created_at,
            )
            for r in usage_rows
        ],
        recent_topups=[
            TopupRow(
                id=r.id,
                amount_eur=_u_to_e(r.amount_eur_micro),
                status=r.status,
                created_at=r.created_at,
                succeeded_at=r.succeeded_at,
            )
            for r in topup_rows
        ],
    )


# ---------------------------------------------------------------------------
# Auto-top-up
# ---------------------------------------------------------------------------

@router.post(
    "/auto-topup",
    response_model=AutoTopupResponse,
    summary="Enable / disable / configure automatic top-up",
    description=(
        "When auto-top-up is enabled and the balance drops below `threshold_eur`, "
        "the next call attempts to charge `amount_eur` to the user's default Stripe "
        "payment method. Both threshold and amount are required if enabled=true."
    ),
)
async def set_auto_topup(
    body: AutoTopupRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AutoTopupResponse:
    if body.enabled:
        if body.threshold_eur is None or body.amount_eur is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "threshold_eur and amount_eur are required when enabled=true",
                    "reason_code": "auto_topup_incomplete",
                },
            )
        if body.amount_eur < 1.0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "amount_eur must be at least 1.0", "reason_code": "amount_below_minimum"},
            )

    fresh = db.query(User).filter(User.id == user.id).first()
    if fresh is None:
        raise HTTPException(status_code=404, detail="user not found")

    fresh.api_auto_topup_enabled = body.enabled
    fresh.api_auto_topup_threshold_micro = (
        int(round(body.threshold_eur * MICRO_PER_EUR)) if body.threshold_eur else None
    )
    fresh.api_auto_topup_amount_micro = (
        int(round(body.amount_eur * MICRO_PER_EUR)) if body.amount_eur else None
    )
    db.commit()
    db.refresh(fresh)

    return AutoTopupResponse(
        enabled=bool(fresh.api_auto_topup_enabled),
        threshold_eur=_u_to_e(fresh.api_auto_topup_threshold_micro) if fresh.api_auto_topup_threshold_micro else None,
        amount_eur=_u_to_e(fresh.api_auto_topup_amount_micro) if fresh.api_auto_topup_amount_micro else None,
    )
