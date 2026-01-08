"""
EU Login Authentication Service

Provides OIDC (OpenID Connect) authentication for EU institutional services:
- EU Login authentication flow
- Token management (access, refresh, ID tokens)
- Automatic token renewal
- Session management
- Support for password and authorization code flows

EU Login Documentation:
https://ecas.ec.europa.eu/cas/help.html
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import httpx
import json
from dataclasses import dataclass, field
import asyncio
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


@dataclass
class EULoginTokens:
    """EU Login authentication tokens"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None
    scope: str = "openid"
    issued_at: datetime = field(default_factory=datetime.now)

    @property
    def is_expired(self) -> bool:
        """Check if access token is expired"""
        expiry = self.issued_at + timedelta(seconds=self.expires_in)
        # Refresh 5 minutes before expiry
        return datetime.now() >= (expiry - timedelta(minutes=5))

    @property
    def authorization_header(self) -> str:
        """Get Authorization header value"""
        return f"{self.token_type} {self.access_token}"


@dataclass
class EULoginUserInfo:
    """EU Login user information"""
    sub: str  # Subject identifier
    email: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    preferred_username: Optional[str] = None
    organization: Optional[str] = None
    department: Optional[str] = None


class EULoginService:
    """
    EU Login OIDC authentication service

    Supports:
    - Resource Owner Password Credentials flow (for service accounts)
    - Authorization Code flow (for user authentication)
    - Token refresh and automatic renewal
    - User info retrieval
    - Session management
    """

    # EU Login OIDC endpoints
    ISSUER_URL = "https://ecas.ec.europa.eu/cas/oauth2"
    AUTHORIZATION_ENDPOINT = f"{ISSUER_URL}/authorize"
    TOKEN_ENDPOINT = f"{ISSUER_URL}/token"
    USERINFO_ENDPOINT = f"{ISSUER_URL}/userinfo"
    REVOCATION_ENDPOINT = f"{ISSUER_URL}/revoke"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize EU Login service

        Args:
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            username: Service account username (for password flow)
            password: Service account password (for password flow)
            redirect_uri: Redirect URI (for authorization code flow)
            timeout: Request timeout in seconds
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.redirect_uri = redirect_uri
        self.timeout = timeout

        # Token storage
        self._tokens: Optional[EULoginTokens] = None
        self._user_info: Optional[EULoginUserInfo] = None
        self._token_refresh_task: Optional[asyncio.Task] = None

        # HTTP client
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True
        )

        logger.info("Initialized EU Login service")

    async def authenticate_with_password(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> EULoginTokens:
        """
        Authenticate using Resource Owner Password Credentials flow

        This flow is suitable for service accounts and backend integrations.

        Args:
            username: EU Login username (optional if set in __init__)
            password: EU Login password (optional if set in __init__)

        Returns:
            Authentication tokens
        """
        auth_username = username or self.username
        auth_password = password or self.password

        if not auth_username or not auth_password:
            raise ValueError("Username and password are required")

        logger.info(f"Authenticating with EU Login (username: {auth_username})")

        # Token request
        data = {
            "grant_type": "password",
            "username": auth_username,
            "password": auth_password,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "openid profile email"
        }

        try:
            response = await self.client.post(
                self.TOKEN_ENDPOINT,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            token_data = response.json()

        except httpx.HTTPError as e:
            logger.error(f"EU Login authentication failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise

        # Create tokens object
        self._tokens = EULoginTokens(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data.get("expires_in", 3600),
            refresh_token=token_data.get("refresh_token"),
            id_token=token_data.get("id_token"),
            scope=token_data.get("scope", "openid"),
            issued_at=datetime.now()
        )

        logger.info("Successfully authenticated with EU Login")

        # Start automatic token refresh
        await self._start_token_refresh()

        return self._tokens

    async def authenticate_with_code(
        self,
        authorization_code: str,
        redirect_uri: Optional[str] = None
    ) -> EULoginTokens:
        """
        Exchange authorization code for tokens (Authorization Code flow)

        This flow is suitable for user authentication in web applications.

        Args:
            authorization_code: Authorization code from redirect
            redirect_uri: Redirect URI (optional if set in __init__)

        Returns:
            Authentication tokens
        """
        auth_redirect_uri = redirect_uri or self.redirect_uri

        if not auth_redirect_uri:
            raise ValueError("Redirect URI is required")

        logger.info("Exchanging authorization code for tokens")

        # Token request
        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": auth_redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        try:
            response = await self.client.post(
                self.TOKEN_ENDPOINT,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            token_data = response.json()

        except httpx.HTTPError as e:
            logger.error(f"Token exchange failed: {str(e)}")
            raise

        # Create tokens object
        self._tokens = EULoginTokens(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data.get("expires_in", 3600),
            refresh_token=token_data.get("refresh_token"),
            id_token=token_data.get("id_token"),
            scope=token_data.get("scope", "openid"),
            issued_at=datetime.now()
        )

        logger.info("Successfully obtained tokens from authorization code")

        # Start automatic token refresh
        await self._start_token_refresh()

        return self._tokens

    def get_authorization_url(
        self,
        state: Optional[str] = None,
        scope: str = "openid profile email"
    ) -> str:
        """
        Generate authorization URL for user redirect

        Args:
            state: CSRF protection state parameter
            scope: OAuth2 scopes to request

        Returns:
            Authorization URL
        """
        if not self.redirect_uri:
            raise ValueError("Redirect URI is required")

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": scope
        }

        if state:
            params["state"] = state

        return f"{self.AUTHORIZATION_ENDPOINT}?{urlencode(params)}"

    async def refresh_access_token(self) -> EULoginTokens:
        """
        Refresh access token using refresh token

        Returns:
            New tokens
        """
        if not self._tokens or not self._tokens.refresh_token:
            raise ValueError("No refresh token available")

        logger.info("Refreshing access token")

        # Refresh request
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._tokens.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        try:
            response = await self.client.post(
                self.TOKEN_ENDPOINT,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            token_data = response.json()

        except httpx.HTTPError as e:
            logger.error(f"Token refresh failed: {str(e)}")
            # Clear tokens on refresh failure
            self._tokens = None
            raise

        # Update tokens
        self._tokens = EULoginTokens(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data.get("expires_in", 3600),
            refresh_token=token_data.get("refresh_token", self._tokens.refresh_token),
            id_token=token_data.get("id_token", self._tokens.id_token),
            scope=token_data.get("scope", self._tokens.scope),
            issued_at=datetime.now()
        )

        logger.info("Successfully refreshed access token")
        return self._tokens

    async def get_user_info(self) -> EULoginUserInfo:
        """
        Retrieve user information from UserInfo endpoint

        Returns:
            User information
        """
        if not self._tokens:
            raise ValueError("Not authenticated")

        # Check if token needs refresh
        if self._tokens.is_expired:
            await self.refresh_access_token()

        logger.debug("Fetching user info from EU Login")

        try:
            response = await self.client.get(
                self.USERINFO_ENDPOINT,
                headers={"Authorization": self._tokens.authorization_header}
            )
            response.raise_for_status()
            user_data = response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch user info: {str(e)}")
            raise

        # Parse user info
        self._user_info = EULoginUserInfo(
            sub=user_data["sub"],
            email=user_data.get("email"),
            given_name=user_data.get("given_name"),
            family_name=user_data.get("family_name"),
            preferred_username=user_data.get("preferred_username"),
            organization=user_data.get("organization"),
            department=user_data.get("department")
        )

        return self._user_info

    async def revoke_token(self, token: Optional[str] = None):
        """
        Revoke access or refresh token

        Args:
            token: Token to revoke (defaults to current access token)
        """
        revoke_token = token or (self._tokens.access_token if self._tokens else None)

        if not revoke_token:
            raise ValueError("No token to revoke")

        logger.info("Revoking token")

        data = {
            "token": revoke_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        try:
            response = await self.client.post(
                self.REVOCATION_ENDPOINT,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()

        except httpx.HTTPError as e:
            logger.warning(f"Token revocation failed: {str(e)}")

        # Clear local tokens
        self._tokens = None
        self._user_info = None

        logger.info("Token revoked successfully")

    async def get_access_token(self) -> str:
        """
        Get current valid access token (refresh if needed)

        Returns:
            Valid access token
        """
        if not self._tokens:
            # Try to authenticate if credentials are available
            if self.username and self.password:
                await self.authenticate_with_password()
            else:
                raise ValueError("Not authenticated")

        # Refresh if expired
        if self._tokens.is_expired:
            await self.refresh_access_token()

        return self._tokens.access_token

    async def get_authorization_header(self) -> str:
        """
        Get Authorization header value with valid token

        Returns:
            Authorization header value (e.g., "Bearer abc123")
        """
        token = await self.get_access_token()
        return f"Bearer {token}"

    async def _start_token_refresh(self):
        """Start background task for automatic token refresh"""
        if self._token_refresh_task:
            self._token_refresh_task.cancel()

        async def refresh_loop():
            while self._tokens:
                try:
                    # Calculate sleep time (refresh 5 minutes before expiry)
                    sleep_time = max(1, self._tokens.expires_in - 300)
                    await asyncio.sleep(sleep_time)

                    if self._tokens and self._tokens.is_expired:
                        await self.refresh_access_token()

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Token refresh loop error: {str(e)}")
                    await asyncio.sleep(60)  # Retry in 1 minute

        self._token_refresh_task = asyncio.create_task(refresh_loop())

    @property
    def is_authenticated(self) -> bool:
        """Check if currently authenticated with valid token"""
        return self._tokens is not None and not self._tokens.is_expired

    async def close(self):
        """Close HTTP client and cancel refresh task"""
        if self._token_refresh_task:
            self._token_refresh_task.cancel()

        await self.client.aclose()
        logger.info("Closed EU Login service")
