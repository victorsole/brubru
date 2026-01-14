"""
Stripe Payment Integration

Handles subscription checkout, webhooks, and customer portal.
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

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(prefix="/stripe", tags=["stripe-payments"])


# Price ID mapping
PRICE_IDS = {
    "yellow_monthly": settings.STRIPE_YELLOW_MONTHLY_PRICE_ID,
    "yellow_annual": settings.STRIPE_YELLOW_ANNUAL_PRICE_ID,
    "blue_monthly": settings.STRIPE_BLUE_MONTHLY_PRICE_ID,
}


@router.post("/create-checkout-session")
async def create_checkout_session(
    tier: str,
    billing_period: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create Stripe Checkout Session for subscription upgrade
    """

    # Validate tier and billing period
    if tier not in ["yellow", "blue"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tier"
        )

    if tier == "blue" and billing_period != "monthly":
        billing_period = "monthly"  # Blue tier only supports monthly

    # Get price ID
    price_key = f"{tier}_{billing_period}"
    price_id = PRICE_IDS.get(price_key)

    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Price not configured for {price_key}"
        )

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
        print("⚠️  WARNING: STRIPE_WEBHOOK_SECRET not set. Webhook verification disabled!")
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

    print(f"📥 Received Stripe webhook: {event['type']}")

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


async def handle_checkout_completed(session, db: Session):
    """Handle successful checkout"""
    user_id = session["metadata"]["user_id"]
    tier = session["metadata"]["tier"]

    print(f"✅ Checkout completed for user {user_id}, tier: {tier}")

    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.subscription_tier = tier
        user.stripe_subscription_id = session.get("subscription")
        db.commit()
        print(f"✅ User {user.email} upgraded to {tier} tier")


async def handle_subscription_updated(subscription, db: Session):
    """Handle subscription updates"""
    customer_id = subscription["customer"]

    print(f"🔄 Subscription updated for customer {customer_id}")

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        # Update subscription expiration
        current_period_end = subscription["current_period_end"]
        user.subscription_expires_at = datetime.fromtimestamp(current_period_end)

        # Check if subscription is active
        if subscription["status"] not in ["active", "trialing"]:
            user.subscription_tier = "white"
            print(f"⚠️  Subscription inactive for {user.email}, downgraded to white")

        db.commit()


async def handle_subscription_deleted(subscription, db: Session):
    """Handle subscription cancellation"""
    customer_id = subscription["customer"]

    print(f"❌ Subscription deleted for customer {customer_id}")

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        user.subscription_tier = "white"
        user.subscription_expires_at = None
        user.stripe_subscription_id = None
        db.commit()
        print(f"✅ User {user.email} downgraded to white tier")


async def handle_payment_succeeded(invoice, db: Session):
    """Handle successful payment"""
    customer_id = invoice["customer"]

    print(f"💰 Payment succeeded for customer {customer_id}")

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        # Extend subscription
        if invoice.get("lines", {}).get("data"):
            period_end = invoice["lines"]["data"][0]["period"]["end"]
            user.subscription_expires_at = datetime.fromtimestamp(period_end)
            db.commit()
            print(f"✅ Subscription extended for {user.email} until {user.subscription_expires_at}")


async def handle_payment_failed(invoice, db: Session):
    """Handle failed payment"""
    customer_id = invoice["customer"]

    print(f"⚠️  Payment failed for customer {customer_id}")

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        # TODO: Send email notification to user
        print(f"⚠️  Payment failed for {user.email} - notification should be sent")
