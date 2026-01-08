"""
Subscription Schemas

Pydantic models for subscription management.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class SubscriptionTier(BaseModel):
    """Subscription tier information"""
    id: str
    name: str
    price_monthly: float
    price_annual: Optional[float]
    description: str
    features: List[str]
    limits: Dict[str, Any]
    custom_pricing: Optional[bool] = False
    minimum_users: Optional[int] = None


class UsageStats(BaseModel):
    """User usage statistics"""
    amendments_used: int
    amendments_limit: int  # -1 for unlimited
    saved_searches_used: int
    saved_searches_limit: int
    api_calls_used: int
    api_calls_limit: int  # -1 for unlimited
    current_tier: str
    subscription_expires_at: Optional[datetime]
    can_upgrade: bool


class UpgradeRequest(BaseModel):
    """Subscription upgrade request"""
    tier: str = Field(..., pattern="^(yellow|blue)$")
    billing_period: str = Field(..., pattern="^(monthly|annual)$")


class FeatureAccessResponse(BaseModel):
    """Feature access check response"""
    feature: str
    has_access: bool
    current_tier: str
    required_tier: Optional[str] = None
