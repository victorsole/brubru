"""
Authentication API Endpoints

Handles user registration, login, OAuth, and token management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import httpx
import hashlib
import json as _json

from core.database import get_db
from core.config import settings
from models.user import User
from schemas.auth_schemas import (
    UserCreate, UserLogin, UserResponse, Token, UserUpdate,
    GoogleAuthRequest, LinkedInAuthRequest, LinkedInCallbackRequest
)
from services.outreach import auto_link_user_if_match

router = APIRouter(prefix="/auth", tags=["authentication"])

# Password hashing - using SHA256 to avoid bcrypt 72-byte limitation
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# JWT settings
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    return user


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register new user with email and password"""

    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        organization=user_data.organization,
        subscription_tier="white",  # Default to free tier
        is_active=True,
        is_verified=False  # Email verification pending
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Outreach auto-link: if this email's domain matches an active campaign,
    # flip private_guide_status='ready' and point at the matching slug.
    # Safe no-op if no match; never blocks signup (errors are swallowed).
    auto_link_user_if_match(db, new_user.id, new_user.email)
    db.refresh(new_user)

    return new_user


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login with email and password"""

    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Capture previous login before updating
    previous_last_login = user.last_login

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
        "previous_last_login": previous_last_login
    }


@router.post("/google", response_model=Token)
async def google_auth(
    auth_request: GoogleAuthRequest,
    db: Session = Depends(get_db)
):
    """Authenticate with Google OAuth"""

    # Verify Google ID token (JWT)
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={auth_request.access_token}"
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google token"
            )

        google_user = response.json()

        # Verify the token is for our client
        expected_client_id = settings.GOOGLE_CLIENT_ID
        if google_user.get("aud") != expected_client_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google token audience"
            )

    email = google_user.get("email")
    name = google_user.get("name")
    avatar_url = google_user.get("picture")

    # Find or create user
    user = db.query(User).filter(User.email == email).first()

    previous_last_login = None

    is_new_user = user is None
    if not user:
        # Create new user
        user = User(
            email=email,
            full_name=name,
            avatar_url=avatar_url,
            subscription_tier="white",
            is_active=True,
            is_verified=True,  # Google email already verified
            oauth_provider="google"
        )
        db.add(user)
    else:
        # Capture previous login before updating
        previous_last_login = user.last_login
        user.last_login = datetime.utcnow()
        if avatar_url:
            user.avatar_url = avatar_url

    db.commit()
    db.refresh(user)

    if is_new_user:
        auto_link_user_if_match(db, user.id, user.email)
        db.refresh(user)

    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
        "previous_last_login": previous_last_login
    }


@router.post("/linkedin/callback", response_model=Token)
async def linkedin_callback(
    callback_request: LinkedInCallbackRequest,
    db: Session = Depends(get_db)
):
    """Handle LinkedIn OAuth callback and exchange code for token"""

    # Exchange authorization code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "authorization_code",
                "code": callback_request.code,
                "redirect_uri": callback_request.redirect_uri,
                "client_id": settings.LINKEDIN_CLIENT_ID,
                "client_secret": settings.LINKEDIN_CLIENT_SECRET
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        if token_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to exchange LinkedIn code for token"
            )

        tokens = token_response.json()
        access_token = tokens.get("access_token")

        # Get user info with access token
        user_response = await client.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if user_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to get LinkedIn user info"
            )

        linkedin_user = user_response.json()

    email = linkedin_user.get("email")
    name = linkedin_user.get("name")
    avatar_url = linkedin_user.get("picture")

    # Find or create user
    user = db.query(User).filter(User.email == email).first()

    previous_last_login = None

    is_new_user = user is None
    if not user:
        user = User(
            email=email,
            full_name=name,
            avatar_url=avatar_url,
            subscription_tier="white",
            is_active=True,
            is_verified=True,
            oauth_provider="linkedin"
        )
        db.add(user)
    else:
        # Capture previous login before updating
        previous_last_login = user.last_login
        user.last_login = datetime.utcnow()
        if avatar_url:
            user.avatar_url = avatar_url

    db.commit()
    db.refresh(user)

    if is_new_user:
        auto_link_user_if_match(db, user.id, user.email)
        db.refresh(user)

    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
        "previous_last_login": previous_last_login
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information"""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_user_profile(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user profile"""

    # Update fields if provided
    if update_data.full_name is not None:
        current_user.full_name = update_data.full_name
    if update_data.organization is not None:
        current_user.organization = update_data.organization
    if update_data.country is not None:
        current_user.country = update_data.country
    pi_changed = False
    if update_data.policy_interests is not None:
        # Frontend sends JSON.stringify([...]), but the column is JSONB.
        # Parse first so we store as a proper JSON array (not a JSON-encoded
        # string). Falls back to the raw value if it doesn't parse.
        raw = update_data.policy_interests
        try:
            parsed = _json.loads(raw) if isinstance(raw, str) else raw
            current_user.policy_interests = (
                parsed if isinstance(parsed, list) else raw
            )
        except (_json.JSONDecodeError, ValueError, TypeError):
            current_user.policy_interests = raw
        pi_changed = True
    # P1b — Monitoring overhaul (May 2026)
    if update_data.role_title is not None:
        current_user.role_title = update_data.role_title
    if update_data.sectors is not None:
        current_user.sectors = update_data.sectors
    # Personalisation fields
    if update_data.first_name is not None:
        current_user.first_name = update_data.first_name
    if update_data.preferred_name is not None:
        current_user.preferred_name = update_data.preferred_name
    if update_data.timezone is not None:
        current_user.timezone = update_data.timezone
    if update_data.language is not None:
        current_user.language = update_data.language
    if update_data.background_preference is not None:
        current_user.background_preference = update_data.background_preference

    current_user.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(current_user)

    # When Policy Interests change, auto-populate My Tracked Files (Section 1 -> 2).
    # Best-effort: a sync failure must never break the profile save.
    if pi_changed:
        try:
            from services.tracking.tracked_files_seeder import sync_tracked_files_from_interests
            sync_tracked_files_from_interests(db, current_user)
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).warning(
                "Tracked-files auto-sync failed for %s: %s", current_user.email, exc
            )

    return current_user


@router.post("/refresh", response_model=Token)
async def refresh_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Refresh access token"""

    # Create new access token
    access_token = create_access_token(
        data={"sub": str(current_user.id), "email": current_user.email}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": current_user
    }


@router.post("/link-preuser")
async def link_preuser_chats(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Link anonymous pre-user chats to the newly registered user."""
    pre_user_id = data.get("pre_user_id")
    if not pre_user_id:
        return {"linked": 0}

    result = db.execute(
        text("UPDATE chats SET user_id = :user_id WHERE pre_user_id = :pre_user_id AND user_id IS NULL"),
        {"user_id": str(current_user.id), "pre_user_id": pre_user_id},
    )
    db.commit()
    return {"linked": result.rowcount}


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout (client should delete token)"""
    return {"message": "Successfully logged out"}
