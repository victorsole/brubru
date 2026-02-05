"""
Admin Authorization

Helper functions and dependencies for admin-only endpoints.
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.auth import get_current_user


def get_current_admin_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to verify user is an admin.

    Only allows users with role='admin' to access protected endpoints.
    Currently, only hello@beresol.eu has admin access.

    Usage:
        @router.get("/admin/endpoint")
        def admin_only(admin: User = Depends(get_current_admin_user)):
            ...

    Raises:
        HTTPException 403: If user is not an admin
    """
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required. This endpoint is restricted to administrators only."
        )

    return current_user


def is_admin(user: User) -> bool:
    """
    Check if a user has admin privileges.

    Args:
        user: User object to check

    Returns:
        True if user is an admin, False otherwise
    """
    return user.role == 'admin'
