"""
Stripe Payment Integration

Handles subscription checkout, webhooks, and customer portal.
Supports the modular pricing model (9 products, 18 prices).
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
import stripe
from datetime import datetime, timedelta
from typing import Optional

from core.config import settings
from core.database import get_db
from models.user import User
from api.auth import get_current_user
from schemas.subscription_schemas import UpgradeRequest

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(prefix="/stripe", tags=["stripe-payments"])


# --- Price ID mapping ---
# Each plan has a monthly and annual price.
# Plans map to internal tiers for feature gating (yellow or blue).

PRICE_IDS = {
    # Individual modules
    "chat_monthly": settings.STRIPE_CHAT_MONTHLY_PRICE_ID,
    "chat_annual": settings.STRIPE_CHAT_ANNUAL_PRICE_ID,
    "bubble_monthly": settings.STRIPE_BUBBLE_MONTHLY_PRICE_ID,
    "bubble_annual": settings.STRIPE_BUBBLE_ANNUAL_PRICE_ID,
    "amendator_monthly": settings.STRIPE_AMENDATOR_MONTHLY_PRICE_ID,
    "amendator_annual": settings.STRIPE_AMENDATOR_ANNUAL_PRICE_ID,
    "comply_monthly": settings.STRIPE_COMPLY_MONTHLY_PRICE_ID,
    "comply_annual": settings.STRIPE_COMPLY_ANNUAL_PRICE_ID,
    "tenderator_monthly": settings.STRIPE_TENDERATOR_MONTHLY_PRICE_ID,
    "tenderator_annual": settings.STRIPE_TENDERATOR_ANNUAL_PRICE_ID,
    # Bundles
    "starter_monthly": settings.STRIPE_STARTER_MONTHLY_PRICE_ID,
    "starter_annual": settings.STRIPE_STARTER_ANNUAL_PRICE_ID,
    "advocate_monthly": settings.STRIPE_ADVOCATE_MONTHLY_PRICE_ID,
    "advocate_annual": settings.STRIPE_ADVOCATE_ANNUAL_PRICE_ID,
    "professional_monthly": settings.STRIPE_PROFESSIONAL_MONTHLY_PRICE_ID,
    "professional_annual": settings.STRIPE_PROFESSIONAL_ANNUAL_PRICE_ID,
    # EP Plan (APAs/MEPs)
    "ep_monthly": settings.STRIPE_EP_MONTHLY_PRICE_ID,
    "ep_annual": settings.STRIPE_EP_ANNUAL_PRICE_ID,
}

# Map Stripe Price IDs back to plan names (for webhook processing)
PRICE_ID_TO_PLAN = {v: k.rsplit("_", 1)[0] for k, v in PRICE_IDS.items() if v}

# Map plan names to internal tier for feature gating
PLAN_TO_TIER = {
    "chat": "yellow",
    "bubble": "yellow",
    "amendator": "yellow",
    "comply": "yellow",
    "tenderator": "yellow",
    "starter": "yellow",
    "advocate": "yellow",
    "ep": "yellow",
    "professional": "blue",
}


@router.post("/create-checkout-session")
async def create_checkout_session(
    request: UpgradeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create Stripe Checkout Session for subscription.

    Accepts JSON body with:
    - plan: one of chat, bubble, amendator, comply, tenderator,
            starter, advocate, professional, ep
    - billing_period: "monthly" or "annual"
    """
    plan = request.plan
    billing_period = request.billing_period

    # Get price ID
    price_key = f"{plan}_{billing_period}"
    price_id = PRICE_IDS.get(price_key)

    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Price not configured for {price_key}"
        )

    # Determine the tier this plan maps to
    tier = PLAN_TO_TIER.get(plan, "yellow")

    try:
        # Create or get Stripe customer
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.full_name,
                metadata={
                    "user_id": str(current_user.id),
                    "organization": current_user.organization or ""
                }
            )
            current_user.stripe_customer_id = customer.id
            db.commit()
            customer_id = customer.id
        else:
            customer_id = current_user.stripe_customer_id

        # Create Checkout Session
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            success_url=f"{settings.APP_URL}/profile?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.APP_URL}/subscription?checkout=canceled",
            metadata={
                "user_id": str(current_user.id),
                "plan": plan,
                "tier": tier,
                "billing_period": billing_period
            },
            allow_promotion_codes=True,
            billing_address_collection="auto",
            customer_update={
                "address": "auto"
            }
        )

        return {
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id
        }

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/create-portal-session")
async def create_portal_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create Stripe Customer Portal session for managing subscription
    """

    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription found"
        )

    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=f"{settings.APP_URL}/profile"
        )

        return {
            "portal_url": portal_session.url
        }

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle Stripe webhook events
    """

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # If webhook secret is not configured, skip verification (development only)
    if not settings.STRIPE_WEBHOOK_SECRET:
        print("[WARN] STRIPE_WEBHOOK_SECRET not set. Webhook verification disabled!")
        import json
        event = json.loads(payload)
    else:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")

    print(f"[WEBHOOK] Received Stripe webhook: {event['type']}")

    # Handle different event types
    if event["type"] == "checkout.session.completed":
        await handle_checkout_completed(event["data"]["object"], db)

    elif event["type"] == "customer.subscription.updated":
        await handle_subscription_updated(event["data"]["object"], db)

    elif event["type"] == "customer.subscription.deleted":
        await handle_subscription_deleted(event["data"]["object"], db)

    elif event["type"] == "invoice.payment_succeeded":
        await handle_payment_succeeded(event["data"]["object"], db)

    elif event["type"] == "invoice.payment_failed":
        await handle_payment_failed(event["data"]["object"], db)

    return {"status": "success"}


def _resolve_tier_from_subscription(subscription) -> tuple[str, str]:
    """
    Resolve the plan name and tier from a Stripe subscription object.
    Looks at the price ID on the subscription items.

    Returns (plan_name, tier).
    """
    items = subscription.get("items", {}).get("data", [])
    if not items:
        return ("unknown", "yellow")

    price_id = items[0].get("price", {}).get("id", "")
    plan = PRICE_ID_TO_PLAN.get(price_id, "unknown")
    tier = PLAN_TO_TIER.get(plan, "yellow")
    return (plan, tier)


async def handle_checkout_completed(session, db: Session):
    """Handle successful checkout"""
    user_id = session["metadata"].get("user_id")
    plan = session["metadata"].get("plan", "unknown")
    tier = session["metadata"].get("tier", "yellow")

    print(f"[OK] Checkout completed for user {user_id}, plan: {plan}, tier: {tier}")

    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.subscription_tier = tier
        user.stripe_subscription_id = session.get("subscription")
        db.commit()
        print(f"[OK] User {user.email} subscribed to {plan} (tier: {tier})")


async def handle_subscription_updated(subscription, db: Session):
    """Handle subscription updates (plan changes, renewals)"""
    customer_id = subscription["customer"]

    plan, tier = _resolve_tier_from_subscription(subscription)
    print(f"[UPDATE] Subscription updated for customer {customer_id}, plan: {plan}, tier: {tier}")

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        # Update subscription expiration
        current_period_end = subscription["current_period_end"]
        user.subscription_expires_at = datetime.fromtimestamp(current_period_end)

        # Check if subscription is active
        if subscription["status"] in ["active", "trialing"]:
            user.subscription_tier = tier
        else:
            user.subscription_tier = "white"
            print(f"[WARN] Subscription inactive for {user.email}, downgraded to white")

        db.commit()


async def handle_subscription_deleted(subscription, db: Session):
    """Handle subscription cancellation"""
    customer_id = subscription["customer"]

    print(f"[CANCEL] Subscription deleted for customer {customer_id}")

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        user.subscription_tier = "white"
        user.subscription_expires_at = None
        user.stripe_subscription_id = None
        db.commit()
        print(f"[OK] User {user.email} downgraded to white tier")


async def handle_payment_succeeded(invoice, db: Session):
    """Handle successful payment"""
    customer_id = invoice["customer"]

    print(f"[PAYMENT] Payment succeeded for customer {customer_id}")

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        # Extend subscription
        if invoice.get("lines", {}).get("data"):
            period_end = invoice["lines"]["data"][0]["period"]["end"]
            user.subscription_expires_at = datetime.fromtimestamp(period_end)
            db.commit()
            print(f"[OK] Subscription extended for {user.email} until {user.subscription_expires_at}")


async def handle_payment_failed(invoice, db: Session):
    """Handle failed payment"""
    customer_id = invoice["customer"]

    print(f"[WARN] Payment failed for customer {customer_id}")

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        # TODO: Send email notification to user
        print(f"[WARN] Payment failed for {user.email} - notification should be sent")
