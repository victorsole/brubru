"""
Authentication Schemas

Pydantic models for authentication requests and responses.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
from uuid import UUID


class UserCreate(BaseModel):
    """User registration schema"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = Field(None, max_length=200)
    organization: Optional[str] = Field(None, max_length=200)

    @field_validator('password')
    @classmethod
    def password_strength(cls, v):
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        return v


class UserLogin(BaseModel):
    """User login schema"""
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    """Google OAuth authentication request"""
    access_token: str
    # If set, the new OAuth identity merges into the dormant row identified
    # by this claim_token instead of creating a fresh user. Powers the
    # pre-provisioned profile flow (migration 148, 18 Jun 2026).
    claim_token: Optional[str] = None


class LinkedInAuthRequest(BaseModel):
    """LinkedIn OAuth authentication request"""
    access_token: str


class LinkedInCallbackRequest(BaseModel):
    """LinkedIn OAuth callback request"""
    code: str
    redirect_uri: str
    # See GoogleAuthRequest.claim_token.
    claim_token: Optional[str] = None


class ClaimPasswordRequest(BaseModel):
    """Set email + password for a dormant pre-provisioned profile."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)

    @field_validator('password')
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        return v


class ClaimInfoResponse(BaseModel):
    """Public-safe info shown on the /claim/<token> landing page."""
    valid: bool
    first_name: Optional[str] = None
    full_name: Optional[str] = None
    organization: Optional[str] = None
    role_title: Optional[str] = None
    pre_provisioned_at: Optional[datetime] = None
    subscription_tier: Optional[str] = None
    private_guide_status: Optional[str] = None
    reason: Optional[str] = None  # populated when valid=false: expired | already_claimed | not_found


class UserUpdate(BaseModel):
    """User profile update schema"""
    full_name: Optional[str] = Field(None, max_length=200)
    organization: Optional[str] = Field(None, max_length=200)
    country: Optional[str] = Field(None, max_length=2)
    policy_interests: Optional[str] = None  # JSON string of policy areas
    # P1b — Monitoring overhaul (May 2026)
    role_title: Optional[str] = Field(None, max_length=120)
    sectors: Optional[list[str]] = None  # sector slugs from controlled vocab
    # Personalisation fields
    first_name: Optional[str] = Field(None, max_length=100)
    preferred_name: Optional[str] = Field(None, max_length=100)
    timezone: Optional[str] = Field(None, max_length=100)
    language: Optional[str] = Field(None, max_length=10)
    background_preference: Optional[str] = Field(None, max_length=100)


class UserResponse(BaseModel):
    """User response schema"""
    id: UUID
    email: str
    full_name: Optional[str]
    first_name: Optional[str]
    preferred_name: Optional[str]
    timezone: Optional[str]
    language: Optional[str]
    organization: Optional[str]
    role: str
    avatar_url: Optional[str]
    country: Optional[str]
    policy_interests: Optional[str]
    role_title: Optional[str] = None
    sectors: Optional[list[str]] = None
    background_preference: Optional[str]
    subscription_tier: str
    subscription_expires_at: Optional[datetime]
    created_at: datetime
    last_login: Optional[datetime]
    is_active: bool
    is_verified: bool
    is_trainer: bool = False

    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str
    user: UserResponse
    previous_last_login: Optional[datetime] = None
