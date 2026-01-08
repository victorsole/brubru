"""
API Key Manager

Centralized management of API keys and credentials for EU institutional services:
- Secure storage from environment variables
- Key validation and testing
- Rate limit tracking per API
- Key rotation support
- Audit logging

Manages keys for:
- EUR-Lex SOAP
- TED (Tenders Electronic Daily)
- Data.europa.eu
- EU Login
- PVGIS (Photovoltaic Geographical Information System)
- And other EU institutional APIs
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class APIService(Enum):
    """Supported API services"""
    EURLEX_SOAP = "eurlex_soap"
    TED = "ted"
    DATA_EUROPA = "data_europa"
    EU_LOGIN = "eu_login"
    PVGIS = "pvgis"
    IATE = "iate"
    CORDIS = "cordis"
    EUROSTAT = "eurostat"
    EUROPEAN_PARLIAMENT = "european_parliament"
    PUBLICATIONS_OFFICE = "publications_office"


@dataclass
class APICredentials:
    """API credentials and metadata"""
    service: APIService
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    party_token: Optional[str] = None
    endpoint_url: Optional[str] = None

    # Rate limiting
    rate_limit_calls: Optional[int] = None
    rate_limit_period: int = 60  # seconds

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    last_validated: Optional[datetime] = None
    is_valid: bool = False
    notes: str = ""

    def mask_sensitive(self) -> Dict[str, Any]:
        """Return credentials with masked sensitive data"""
        def mask(value: Optional[str]) -> Optional[str]:
            if not value:
                return None
            if len(value) <= 8:
                return "*" * len(value)
            return f"{value[:4]}...{value[-4:]}"

        return {
            "service": self.service.value,
            "api_key": mask(self.api_key),
            "username": self.username,  # Username is not masked
            "password": "***" if self.password else None,
            "client_id": mask(self.client_id),
            "client_secret": "***" if self.client_secret else None,
            "party_token": mask(self.party_token),
            "endpoint_url": self.endpoint_url,
            "rate_limit_calls": self.rate_limit_calls,
            "rate_limit_period": self.rate_limit_period,
            "is_valid": self.is_valid,
            "last_validated": self.last_validated.isoformat() if self.last_validated else None
        }


@dataclass
class RateLimitState:
    """Rate limit tracking state"""
    service: APIService
    calls_made: int = 0
    period_start: datetime = field(default_factory=datetime.now)
    blocked_until: Optional[datetime] = None


class APIKeyManager:
    """
    Centralized API key and credentials manager

    Features:
    - Load credentials from environment variables
    - Validate API keys
    - Track rate limits per service
    - Support key rotation
    - Audit logging
    """

    # Environment variable mappings
    ENV_MAPPINGS = {
        APIService.EURLEX_SOAP: {
            "username": "EURLEX_SOAP_USERNAME",
            "password": "EURLEX_SOAP_PASSWORD",
            "endpoint_url": "EURLEX_SOAP_ENDPOINT"
        },
        APIService.TED: {
            "api_key": "TED_API_KEY",
            "endpoint_url": "TED_API_ENDPOINT"
        },
        APIService.DATA_EUROPA: {
            "party_token": "DATA_EUROPA_PARTY_TOKEN",
            "endpoint_url": "DATA_EUROPA_ENDPOINT"
        },
        APIService.EU_LOGIN: {
            "client_id": "EU_LOGIN_CLIENT_ID",
            "client_secret": "EU_LOGIN_CLIENT_SECRET",
            "username": "EU_LOGIN_USERNAME",
            "password": "EU_LOGIN_PASSWORD"
        },
        APIService.PVGIS: {
            "endpoint_url": "PVGIS_ENDPOINT",
            "rate_limit_calls": 30,  # 30 calls/second limit
            "rate_limit_period": 1
        },
        APIService.IATE: {
            "endpoint_url": "IATE_ENDPOINT"
        },
        APIService.CORDIS: {
            "endpoint_url": "CORDIS_ENDPOINT"
        },
        APIService.EUROSTAT: {
            "api_key": "EUROSTAT_API_KEY",
            "endpoint_url": "EUROSTAT_ENDPOINT"
        },
        APIService.EUROPEAN_PARLIAMENT: {
            "endpoint_url": "EUROPEAN_PARLIAMENT_ENDPOINT"
        },
        APIService.PUBLICATIONS_OFFICE: {
            "endpoint_url": "PUBLICATIONS_OFFICE_ENDPOINT"
        }
    }

    # Default endpoints
    DEFAULT_ENDPOINTS = {
        APIService.EURLEX_SOAP: "https://eur-lex.europa.eu/EURLexWebService",
        APIService.TED: "https://ted.europa.eu/api",
        APIService.DATA_EUROPA: "https://data.europa.eu/api",
        APIService.EU_LOGIN: "https://ecas.ec.europa.eu/cas/oauth2",
        APIService.PVGIS: "https://re.jrc.ec.europa.eu/api/v5_2",
        APIService.IATE: "https://iate.europa.eu/api",
        APIService.CORDIS: "https://cordis.europa.eu/api",
        APIService.EUROSTAT: "https://ec.europa.eu/eurostat/api",
        APIService.EUROPEAN_PARLIAMENT: "https://data.europarl.europa.eu",
        APIService.PUBLICATIONS_OFFICE: "https://op.europa.eu/api"
    }

    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize API key manager

        Args:
            env_file: Path to .env file (optional)
        """
        self.credentials: Dict[APIService, APICredentials] = {}
        self.rate_limits: Dict[APIService, RateLimitState] = {}

        # Load environment variables from .env file if provided
        if env_file:
            self._load_env_file(env_file)

        # Load all credentials
        self._load_credentials()

        logger.info(f"Initialized API Key Manager with {len(self.credentials)} services")

    def _load_env_file(self, env_file: str):
        """Load environment variables from .env file"""
        env_path = Path(env_file)

        if not env_path.exists():
            logger.warning(f".env file not found: {env_file}")
            return

        logger.info(f"Loading environment variables from {env_file}")

        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]

                    os.environ[key] = value

    def _load_credentials(self):
        """Load credentials from environment variables"""
        for service, env_mapping in self.ENV_MAPPINGS.items():
            creds = APICredentials(service=service)

            # Load credentials from environment
            for cred_field, env_var in env_mapping.items():
                if cred_field in ["rate_limit_calls", "rate_limit_period"]:
                    # These are integers, not env vars
                    setattr(creds, cred_field, env_var)
                else:
                    value = os.getenv(env_var)
                    if value and value not in ["your_", "placeholder", ""]:
                        setattr(creds, cred_field, value)

            # Set default endpoint if not provided
            if not creds.endpoint_url:
                creds.endpoint_url = self.DEFAULT_ENDPOINTS.get(service)

            # Check if credentials are present
            has_auth = (
                creds.api_key or
                creds.party_token or
                (creds.username and creds.password) or
                (creds.client_id and creds.client_secret)
            )

            if has_auth or creds.endpoint_url:
                self.credentials[service] = creds
                logger.debug(f"Loaded credentials for {service.value}")

    def get_credentials(self, service: APIService) -> Optional[APICredentials]:
        """
        Get credentials for a service

        Args:
            service: API service

        Returns:
            Credentials or None if not found
        """
        return self.credentials.get(service)

    def has_credentials(self, service: APIService) -> bool:
        """
        Check if credentials exist for a service

        Args:
            service: API service

        Returns:
            True if credentials exist
        """
        creds = self.get_credentials(service)
        if not creds:
            return False

        return bool(
            creds.api_key or
            creds.party_token or
            (creds.username and creds.password) or
            (creds.client_id and creds.client_secret)
        )

    def set_credentials(
        self,
        service: APIService,
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        party_token: Optional[str] = None,
        endpoint_url: Optional[str] = None
    ):
        """
        Manually set credentials for a service

        Args:
            service: API service
            api_key: API key
            username: Username
            password: Password
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            party_token: Party token
            endpoint_url: API endpoint URL
        """
        if service not in self.credentials:
            self.credentials[service] = APICredentials(service=service)

        creds = self.credentials[service]

        if api_key is not None:
            creds.api_key = api_key
        if username is not None:
            creds.username = username
        if password is not None:
            creds.password = password
        if client_id is not None:
            creds.client_id = client_id
        if client_secret is not None:
            creds.client_secret = client_secret
        if party_token is not None:
            creds.party_token = party_token
        if endpoint_url is not None:
            creds.endpoint_url = endpoint_url

        logger.info(f"Updated credentials for {service.value}")

    def check_rate_limit(self, service: APIService) -> bool:
        """
        Check if service is within rate limits

        Args:
            service: API service

        Returns:
            True if within limits, False if rate limited
        """
        creds = self.get_credentials(service)
        if not creds or not creds.rate_limit_calls:
            return True  # No rate limit configured

        # Initialize rate limit state if needed
        if service not in self.rate_limits:
            self.rate_limits[service] = RateLimitState(service=service)

        state = self.rate_limits[service]
        now = datetime.now()

        # Check if blocked
        if state.blocked_until and now < state.blocked_until:
            logger.warning(f"Rate limited for {service.value} until {state.blocked_until}")
            return False

        # Reset counter if period expired
        period_elapsed = (now - state.period_start).total_seconds()
        if period_elapsed >= creds.rate_limit_period:
            state.calls_made = 0
            state.period_start = now
            state.blocked_until = None

        # Check limit
        if state.calls_made >= creds.rate_limit_calls:
            # Block until period ends
            state.blocked_until = state.period_start + timedelta(seconds=creds.rate_limit_period)
            logger.warning(
                f"Rate limit exceeded for {service.value}: "
                f"{state.calls_made}/{creds.rate_limit_calls} calls in {creds.rate_limit_period}s"
            )
            return False

        # Increment counter
        state.calls_made += 1
        return True

    def record_api_call(self, service: APIService):
        """
        Record an API call for rate limiting

        Args:
            service: API service
        """
        self.check_rate_limit(service)  # This updates the counter

    async def validate_credentials(self, service: APIService) -> bool:
        """
        Validate credentials by making a test API call

        Args:
            service: API service

        Returns:
            True if credentials are valid
        """
        creds = self.get_credentials(service)
        if not creds:
            logger.warning(f"No credentials found for {service.value}")
            return False

        # TODO: Implement actual validation calls for each service
        # For now, just check if credentials exist
        is_valid = self.has_credentials(service)

        creds.is_valid = is_valid
        creds.last_validated = datetime.now()

        logger.info(f"Validated credentials for {service.value}: {is_valid}")
        return is_valid

    def get_all_services(self) -> List[APIService]:
        """
        Get list of all configured services

        Returns:
            List of API services with credentials
        """
        return list(self.credentials.keys())

    def get_service_status(self) -> Dict[str, Any]:
        """
        Get status of all services

        Returns:
            Dictionary with service status information
        """
        status = {}

        for service in APIService:
            creds = self.get_credentials(service)

            if creds:
                status[service.value] = {
                    "configured": True,
                    "has_auth": self.has_credentials(service),
                    "endpoint": creds.endpoint_url,
                    "rate_limit": f"{creds.rate_limit_calls}/{creds.rate_limit_period}s"
                        if creds.rate_limit_calls else "None",
                    "validated": creds.last_validated.isoformat() if creds.last_validated else None,
                    "is_valid": creds.is_valid
                }
            else:
                status[service.value] = {
                    "configured": False,
                    "has_auth": False
                }

        return status

    def get_masked_credentials(self, service: APIService) -> Optional[Dict[str, Any]]:
        """
        Get credentials with sensitive data masked (for logging/display)

        Args:
            service: API service

        Returns:
            Masked credentials dictionary
        """
        creds = self.get_credentials(service)
        if not creds:
            return None

        return creds.mask_sensitive()

    def export_required_env_vars(self) -> List[str]:
        """
        Export list of required environment variables

        Returns:
            List of environment variable names that should be set
        """
        env_vars = []

        for service, env_mapping in self.ENV_MAPPINGS.items():
            for cred_field, env_var in env_mapping.items():
                if isinstance(env_var, str) and env_var.isupper():
                    env_vars.append(env_var)

        return sorted(set(env_vars))
