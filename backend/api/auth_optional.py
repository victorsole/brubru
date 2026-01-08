"""
Optional Authentication Helper

Provides development mode authentication bypass when DEVELOPMENT_MODE=true
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional

from ..core.database import get_db
from ..core.config import settings
from ..models.user import User
from .auth import get_current_user as get_current_user_strict

# Optional OAuth2 scheme for development
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current user, but return None instead of raising exception if not authenticated.
    Only use this for endpoints that can work without auth in development mode.
    """
    # Check for no token or invalid token values from frontend
    if not token or token == "null" or token == "undefined":
        # In development mode, create/return a test user
        if settings.DEVELOPMENT_MODE:
            # Get or create test user
            test_user = db.query(User).filter(User.email == "test@brubru.dev").first()
            if not test_user:
                test_user = User(
                    email="test@brubru.dev",
                    full_name="Test User",
                    organization="Brubru Development",
                    role="user",
                    is_active=True,
                    is_verified=True,
                    subscription_tier="blue",  # Give full access for testing
                    policy_interests='["Digital Policy", "Environment", "Trade"]'
                )
                db.add(test_user)
                db.commit()
                db.refresh(test_user)
            return test_user
        return None

    # If token provided, validate it
    try:
        return await get_current_user_strict(token, db)
    except HTTPException:
        return None


async def get_current_user_dev(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current user with development mode fallback.
    Use this for endpoints that should be accessible in development without auth.
    """
    user = await get_current_user_optional(token, db)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in or enable DEVELOPMENT_MODE=true in backend .env",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
