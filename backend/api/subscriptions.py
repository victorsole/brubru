"""
Subscription API Endpoints

Handles subscription tier management, upgrades, and usage tracking.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Dict

from core.database import get_db
from models.user import User
from api.auth import get_current_user
from schemas.subscription_schemas import (
    SubscriptionTier, UsageStats, UpgradeRequest, FeatureAccessResponse
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


# Usage limits per tier
TIER_LIMITS = {
    "white": {
        "amendments_per_month": 5,
        "saved_searches_limit": 5,
        "api_calls_per_month": 0,
        "ai_model": "gpt-3.5-turbo",
        "response_priority": "normal",
        "support": "community",
        "export_formats": ["xml", "html"],  # No PDF/Word
        "watermark": True,
        "features": ["basic_chat", "basic_search", "basic_amendator"]
    },
    "yellow": {
        "amendments_per_month": -1,  # Unlimited
        "saved_searches_limit": -1,  # Unlimited
        "api_calls_per_month": 1000,
        "ai_model": "gpt-4",
        "response_priority": "high",
        "support": "email_48h",
        "export_formats": ["xml", "html", "pdf", "docx"],  # All formats
        "watermark": False,
        "features": ["advanced_ai", "priority_response", "no_watermark", "advanced_search", "rss_alerts", "exports"]
    },
    "blue": {
        "amendments_per_month": -1,  # Unlimited
        "saved_searches_limit": -1,  # Unlimited
        "api_calls_per_month": -1,  # Unlimited
        "ai_model": "gpt-4-turbo",
        "response_priority": "highest",
        "support": "dedicated_24h",
        "export_formats": ["xml", "html", "pdf", "docx"],  # All formats
        "watermark": False,
        "features": ["everything_in_yellow", "multi_user", "custom_domain", "white_label", "sla", "training", "user_preferences"]
    }
}


@router.get("/tiers", response_model=List[SubscriptionTier])
async def get_subscription_tiers():
    """Get all available subscription tiers with pricing"""

    return [
        {
            "id": "white",
            "name": "White (Basic)",
            "price_monthly": 0,
            "price_annual": 0,
            "description": "Free tier with basic functionality",
            "features": TIER_LIMITS["white"]["features"],
            "limits": {
                "amendments_per_month": TIER_LIMITS["white"]["amendments_per_month"],
                "saved_searches_limit": TIER_LIMITS["white"]["saved_searches_limit"],
                "api_calls_per_month": TIER_LIMITS["white"]["api_calls_per_month"]
            }
        },
        {
            "id": "yellow",
            "name": "Yellow (Professional)",
            "price_monthly": 79,
            "price_annual": 790,  # 2 months free
            "description": "Professional tier with advanced AI and unlimited amendments",
            "features": TIER_LIMITS["yellow"]["features"],
            "limits": {
                "amendments_per_month": -1,  # Unlimited
                "saved_searches_limit": -1,  # Unlimited
                "api_calls_per_month": TIER_LIMITS["yellow"]["api_calls_per_month"]
            }
        },
        {
            "id": "blue",
            "name": "Blue (Enterprise)",
            "price_monthly": 599,
            "price_annual": None,  # Custom pricing
            "description": "Enterprise tier with custom domain specialisation",
            "features": TIER_LIMITS["blue"]["features"],
            "limits": {
                "amendments_per_month": -1,
                "saved_searches_limit": -1,
                "api_calls_per_month": -1
            },
            "custom_pricing": True,
            "minimum_users": 5
        }
    ]


@router.get("/usage", response_model=UsageStats)
async def get_usage_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's usage statistics"""

    # TODO: Implement usage tracking in database
    # For now, return mock data

    tier_limits = TIER_LIMITS.get(current_user.subscription_tier, TIER_LIMITS["white"])

    return {
        "amendments_used": 3,  # TODO: Query from database
        "amendments_limit": tier_limits["amendments_per_month"],
        "saved_searches_used": 2,  # TODO: Query from database
        "saved_searches_limit": tier_limits["saved_searches_limit"],
        "api_calls_used": 125,
        "api_calls_limit": tier_limits["api_calls_per_month"],
        "current_tier": current_user.subscription_tier,
        "subscription_expires_at": current_user.subscription_expires_at,
        "can_upgrade": current_user.subscription_tier != "blue"
    }


@router.post("/upgrade")
async def upgrade_subscription(
    upgrade_request: UpgradeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upgrade user subscription tier"""

    # Validate tier
    if upgrade_request.tier not in ["yellow", "blue"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subscription tier"
        )

    # Check if downgrade (not allowed)
    tier_order = ["white", "yellow", "blue"]
    current_tier_index = tier_order.index(current_user.subscription_tier)
    new_tier_index = tier_order.index(upgrade_request.tier)

    if new_tier_index < current_tier_index:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Downgrades not allowed. Please contact support."
        )

    # TODO: Integrate with Mollie payment
    # For now, just update the tier

    current_user.subscription_tier = upgrade_request.tier

    # Set expiration date
    if upgrade_request.billing_period == "monthly":
        current_user.subscription_expires_at = datetime.utcnow() + timedelta(days=30)
    else:  # annual
        current_user.subscription_expires_at = datetime.utcnow() + timedelta(days=365)

    db.commit()
    db.refresh(current_user)

    return {
        "message": f"Successfully upgraded to {upgrade_request.tier} tier",
        "tier": current_user.subscription_tier,
        "expires_at": current_user.subscription_expires_at
    }


@router.get("/features", response_model=FeatureAccessResponse)
async def check_feature_access(
    feature: str,
    current_user: User = Depends(get_current_user)
):
    """Check if user has access to a specific feature"""

    tier_limits = TIER_LIMITS.get(current_user.subscription_tier, TIER_LIMITS["white"])
    features = tier_limits.get("features", [])

    has_access = feature in features or "everything_in_yellow" in features

    return {
        "feature": feature,
        "has_access": has_access,
        "current_tier": current_user.subscription_tier,
        "required_tier": "yellow" if not has_access else current_user.subscription_tier
    }
