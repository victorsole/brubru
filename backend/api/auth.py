"""
Authentication API Endpoints

Handles user registration, login, OAuth, and token management.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
import httpx
import hashlib
import logging
import secrets
import json as _json

from core.database import get_db
from core.config import settings
from models.user import User
from models.password_reset_token import PasswordResetToken
from schemas.auth_schemas import (
    UserCreate, UserLogin, UserResponse, Token, UserUpdate,
    GoogleAuthRequest, LinkedInAuthRequest, LinkedInCallbackRequest,
    ClaimPasswordRequest, ClaimInfoResponse,
    ForgotPasswordRequest, ResetPasswordRequest, MessageResponse,
    ResetTokenCheckResponse,
)
from services.outreach import auto_link_user_if_match

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


# ---------------------------------------------------------------------------
# Dormant pre-provisioned profile claim flow (migration 148, 18 Jun 2026).
# A claim_token in the magic link lets the OAuth callback (or password setup)
# merge the new identity onto a pre-populated dormant row instead of creating
# a fresh user. See backend/migrations/148_dormant_profiles_claim_flow.sql.
# ---------------------------------------------------------------------------


def _lookup_claimable_row(db: Session, claim_token: str) -> tuple[User | None, str | None]:
    """Return (user, error_reason). user is None if not claimable.
    error_reason values: not_found | expired | already_claimed.
    """
    if not claim_token:
        return None, "not_found"
    user = db.query(User).filter(User.claim_token == claim_token).first()
    if not user:
        return None, "not_found"
    if user.claimed_at is not None:
        return None, "already_claimed"
    if user.claim_token_expires_at and user.claim_token_expires_at < datetime.now(timezone.utc):
        return None, "expired"
    return user, None


def _attach_oauth_to_dormant(
    db: Session,
    dormant: User,
    *,
    oauth_provider: str,
    email: str,
    full_name: str | None,
    avatar_url: str | None,
) -> User:
    """Merge the new OAuth identity onto a dormant row. Caller commits."""
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth provider did not return an email",
        )

    existing = (
        db.query(User)
        .filter(User.email == email, User.id != dormant.id)
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A Brubru account already exists for that email. Sign in "
                "there instead, or contact hello@beresol.eu to merge."
            ),
        )

    dormant.email = email
    if full_name and not dormant.full_name:
        dormant.full_name = full_name
    if avatar_url:
        dormant.avatar_url = avatar_url
    dormant.oauth_provider = oauth_provider
    dormant.is_active = True
    dormant.is_verified = True
    dormant.claimed_at = datetime.utcnow()
    dormant.claim_token = None  # single-use
    dormant.claim_token_expires_at = None
    dormant.last_login = datetime.utcnow()
    return dormant

# Password hashing - using SHA256 to avoid bcrypt 72-byte limitation
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# JWT settings
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """Verify password against hash.

    hashed_password is None for OAuth-only accounts, which have no password to
    check. passlib raises on a None hash, so guard it here: the caller wants a
    failed verification, not a 500.
    """
    if not hashed_password:
        return False
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

    previous_last_login = None
    is_new_user = False

    # Pre-provisioned dormant profile claim path (migration 148).
    if auth_request.claim_token:
        dormant, reason = _lookup_claimable_row(db, auth_request.claim_token)
        if dormant is None:
            raise HTTPException(
                status_code=status.HTTP_410_GONE if reason == "expired" else status.HTTP_404_NOT_FOUND,
                detail=f"Claim link is no longer valid ({reason}).",
            )
        user = _attach_oauth_to_dormant(
            db, dormant,
            oauth_provider="google", email=email,
            full_name=name, avatar_url=avatar_url,
        )
        is_new_user = True  # treat as new for downstream hooks
    else:
        # Standard email-keyed merge / create.
        user = db.query(User).filter(User.email == email).first()
        is_new_user = user is None
        if not user:
            user = User(
                email=email,
                full_name=name,
                avatar_url=avatar_url,
                subscription_tier="white",
                is_active=True,
                is_verified=True,
                oauth_provider="google"
            )
            db.add(user)
        else:
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

    previous_last_login = None
    is_new_user = False

    # Pre-provisioned dormant profile claim path (migration 148).
    if callback_request.claim_token:
        dormant, reason = _lookup_claimable_row(db, callback_request.claim_token)
        if dormant is None:
            raise HTTPException(
                status_code=status.HTTP_410_GONE if reason == "expired" else status.HTTP_404_NOT_FOUND,
                detail=f"Claim link is no longer valid ({reason}).",
            )
        user = _attach_oauth_to_dormant(
            db, dormant,
            oauth_provider="linkedin", email=email,
            full_name=name, avatar_url=avatar_url,
        )
        is_new_user = True
    else:
        user = db.query(User).filter(User.email == email).first()
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


# ---------------------------------------------------------------------------
# Claim endpoints (migration 148).
# GET /auth/claim/{token}             - public-safe profile preview
# POST /auth/claim/{token}/password   - password fallback for non-OAuth users
# OAuth callers pass `claim_token` directly into POST /auth/google or
# POST /auth/linkedin/callback.
# ---------------------------------------------------------------------------

@router.get("/claim/{token}", response_model=ClaimInfoResponse)
async def claim_info(token: str, db: Session = Depends(get_db)):
    """Look up the dormant pre-provisioned profile behind a claim link.

    Returns a public-safe preview so the frontend can render
    "Welcome, Antoine - Brubru is preconfigured for you". Does NOT issue
    a session; the actual claim happens on OAuth callback or password POST.
    """
    user, reason = _lookup_claimable_row(db, token)
    if user is None:
        return ClaimInfoResponse(valid=False, reason=reason)
    return ClaimInfoResponse(
        valid=True,
        first_name=user.first_name,
        full_name=user.full_name,
        organization=user.organization,
        role_title=user.role_title,
        pre_provisioned_at=user.pre_provisioned_at,
        subscription_tier=user.subscription_tier,
        private_guide_status=user.private_guide_status,
    )


@router.post("/claim/{token}/password", response_model=Token)
async def claim_with_password(
    token: str,
    body: ClaimPasswordRequest,
    db: Session = Depends(get_db),
):
    """Fallback claim path for prospects who prefer email + password to OAuth.

    Sets the dormant row's email + password_hash, marks claimed_at, returns
    a session token. Mirrors the OAuth claim path (_attach_oauth_to_dormant)
    but does not set oauth_provider.
    """
    dormant, reason = _lookup_claimable_row(db, token)
    if dormant is None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE if reason == "expired" else status.HTTP_404_NOT_FOUND,
            detail=f"Claim link is no longer valid ({reason}).",
        )

    existing = (
        db.query(User)
        .filter(User.email == body.email, User.id != dormant.id)
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A Brubru account already exists for that email. Sign in "
                "there instead, or contact hello@beresol.eu to merge."
            ),
        )

    dormant.email = body.email
    dormant.password_hash = get_password_hash(body.password)
    dormant.is_active = True
    dormant.is_verified = True
    dormant.claimed_at = datetime.utcnow()
    dormant.claim_token = None
    dormant.claim_token_expires_at = None
    dormant.last_login = datetime.utcnow()
    db.commit()
    db.refresh(dormant)

    auto_link_user_if_match(db, dormant.id, dormant.email)
    db.refresh(dormant)

    access_token = create_access_token(
        data={"sub": str(dormant.id), "email": dormant.email}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": dormant,
        "previous_last_login": None,
    }


# ---------------------------------------------------------------------------
# Password reset (migration 211). Entry point is the login page's
# "I forgot my password" link.
#
# Two rules govern the shape of these endpoints:
#   1. No account enumeration. /forgot-password answers identically whether or
#      not the address has an account, so the endpoint cannot be used to test
#      whether someone is a Brubru user.
#   2. The raw token exists only in the email. We persist sha256(token).
# ---------------------------------------------------------------------------

RESET_TOKEN_TTL = timedelta(hours=1)
RESET_REQUESTS_PER_HOUR = 5

# Deliberately says nothing about whether the address is known to us.
GENERIC_RESET_MESSAGE = (
    "If that address has a Brubru account, a reset link is on its way. "
    "It expires in one hour. Remember to check your spam folder."
)


def _hash_reset_token(raw_token: str) -> str:
    """sha256 hex of the raw token. What we store, never the token itself."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _lookup_reset_token(db: Session, raw_token: str) -> tuple[PasswordResetToken | None, str | None]:
    """Return (token_row, error_reason). token_row is None if not redeemable."""
    row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == _hash_reset_token(raw_token))
        .first()
    )
    if row is None:
        return None, "not_found"
    if row.used_at is not None:
        return None, "already_used"
    if not row.is_redeemable:
        return None, "expired"
    return row, None


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Send a password reset link.

    Always returns the same 200 body. A caller cannot tell from the response
    whether the address has an account, whether it is OAuth-only, or whether it
    hit the rate limit.
    """
    # Recovery flows should be forgiving about case, so match case-insensitively
    # and then send to the address as stored.
    email = body.email.strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email).first()

    if user is None or not user.is_active:
        return MessageResponse(message=GENERIC_RESET_MESSAGE)

    # A pre-provisioned row that nobody has claimed yet is not an account, it is
    # an invitation (migration 148). It has an email and no password, so without
    # this guard it would fall through to the normal reset path below and let a
    # reset stand in for the single-use claim token, leaving claimed_at NULL and
    # the claim token still live on an account that now has a password. Dormant
    # rows are reachable only through /claim/<token>.
    if user.pre_provisioned_at is not None and user.claimed_at is None:
        logger.info("[AUTH] Password reset ignored for unclaimed dormant row %s", user.id)
        return MessageResponse(message=GENERIC_RESET_MESSAGE)

    from services.email_service import (
        get_email_service,
        build_password_reset_email,
        build_oauth_only_reset_email,
    )

    email_service = get_email_service()

    # OAuth-only accounts have no password to reset. Tell them in the email
    # rather than in the API response, so the endpoint stays non-enumerable.
    if not user.password_hash and user.oauth_provider:
        content = build_oauth_only_reset_email(user, user.oauth_provider)
        try:
            email_service.send(to=user.email, subject=content["subject"], html_body=content["html_body"])
        except Exception:
            logger.exception("[AUTH] Failed to send OAuth-only reset notice to user %s", user.id)
        return MessageResponse(message=GENERIC_RESET_MESSAGE)

    # Rate limit: cheap count over the index we already need for invalidation.
    window_start = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = (
        db.query(func.count(PasswordResetToken.id))
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.created_at >= window_start,
        )
        .scalar()
    ) or 0
    if recent >= RESET_REQUESTS_PER_HOUR:
        logger.warning("[AUTH] Password reset rate limit hit for user %s", user.id)
        return MessageResponse(message=GENERIC_RESET_MESSAGE)

    # Requesting a new link retires any outstanding ones, so only the newest
    # email in the inbox works.
    (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .update({PasswordResetToken.used_at: datetime.now(timezone.utc)}, synchronize_session=False)
    )

    raw_token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_reset_token(raw_token),
            expires_at=datetime.now(timezone.utc) + RESET_TOKEN_TTL,
            request_ip=(request.client.host if request.client else None),
        )
    )
    db.commit()

    reset_url = f"{settings.APP_URL.rstrip('/')}/reset-password?token={raw_token}"
    content = build_password_reset_email(user, reset_url)
    try:
        email_service.send(to=user.email, subject=content["subject"], html_body=content["html_body"])
    except Exception:
        # The token is already issued; surfacing the failure would leak that the
        # account exists. Log loudly instead.
        logger.exception("[AUTH] Failed to send password reset email to user %s", user.id)

    return MessageResponse(message=GENERIC_RESET_MESSAGE)


@router.get("/reset-password/{token}", response_model=ResetTokenCheckResponse)
async def check_reset_token(token: str, db: Session = Depends(get_db)):
    """Report whether a reset link is still good.

    Lets the page say "this link has expired" before asking for a new password,
    instead of failing after the user has typed one.
    """
    row, reason = _lookup_reset_token(db, token)
    if row is None:
        return ResetTokenCheckResponse(valid=False, reason=reason)
    return ResetTokenCheckResponse(valid=True)


@router.post("/reset-password", response_model=Token)
async def reset_password(
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """Redeem a reset token, set the new password, and sign the user in."""
    row, reason = _lookup_reset_token(db, body.token)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE if reason in ("expired", "already_used")
            else status.HTTP_404_NOT_FOUND,
            detail=f"This reset link is no longer valid ({reason}). Request a new one.",
        )

    user = db.query(User).filter(User.id == row.user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account unavailable")

    now = datetime.now(timezone.utc)
    user.password_hash = get_password_hash(body.password)
    # A user who set a password this way has demonstrably received mail there.
    user.is_verified = True
    user.last_login = datetime.utcnow()
    row.used_at = now

    # Burn every other outstanding token for this user, not just the redeemed one.
    (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .update({PasswordResetToken.used_at: now}, synchronize_session=False)
    )
    db.commit()
    db.refresh(user)

    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
        "previous_last_login": None,
    }


SEEN_THROTTLE_SECONDS = 3600


def touch_last_seen(db: Session, user: User) -> None:
    """Record that this user is present right now (migration 221).

    `last_login` cannot answer "when were they last here": the token lives 7
    days, the frontend persists it, and /auth/refresh mints a new one without
    touching it, so a daily returning user leaves last_login frozen. That is
    how a client on a paid trial was reported as "last used 11 August" when the
    truthful statement was "last re-authenticated 11 August".

    Throttled to once an hour per user so this costs an UPDATE per active user
    per hour, not one per request. Never allowed to break the request it rides
    on -- knowing when someone was last seen is worth strictly less than the
    call succeeding.
    """
    try:
        now = datetime.now(timezone.utc)
        previous = user.last_seen_at
        if previous is not None:
            if previous.tzinfo is None:
                previous = previous.replace(tzinfo=timezone.utc)
            if (now - previous).total_seconds() < SEEN_THROTTLE_SECONDS:
                return
        user.last_seen_at = now
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[auth] could not update last_seen_at for %s: %s: %s",
                       getattr(user, "id", "?"), type(exc).__name__, exc)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user information"""
    touch_last_seen(db, current_user)
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

    # This is the touchpoint that made "who is active" unanswerable: the axios
    # interceptor calls it silently on any 401 and retries, so it is often the
    # ONLY server-side trace a returning user leaves. It deliberately does not
    # move last_login -- refreshing a token is not re-authenticating -- but it
    # is unambiguous evidence of presence. See migration 221.
    touch_last_seen(db, current_user)

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
