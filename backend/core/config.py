"""
Application Configuration

Loads environment variables and provides typed configuration for the application.
"""

from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = ConfigDict(
        env_file=("../.env", ".env"),
        case_sensitive=True,
        extra='ignore'  # Ignore extra fields in .env
    )

    # Application
    APP_NAME: str = "Brubru"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    DEVELOPMENT_MODE: bool = False  # Enable development mode authentication bypass
    SECRET_KEY: str
    CRON_SECRET: str | None = None  # Secret key for cron job authentication

    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str  # Anon key (safe for frontend)
    SUPABASE_SERVICE_KEY: str  # Service role key (backend only)
    DATABASE_URL: str  # PostgreSQL connection string

    # AI Services
    MISTRAL_API_KEY: str | None = None  # Mistral (primary - cost-effective)
    ANTHROPIC_API_KEY: str  # Claude (fallback 1)
    OPENAI_API_KEY: str  # GPT-4 (fallback 2)
    OPENAI_ORG_ID: str | None = None
    GOOGLE_GEMINI_API_KEY: str | None = None  # Gemini (fallback 3)

    # MCP Toolbox for Databases
    TOOLBOX_URL: str = "http://localhost:5000"  # GenAI Toolbox server URL

    # Hugging Face
    HUGGINGFACE_API_KEY: str | None = None  # Optional, for Inference API
    HF_DEFAULT_MODEL: str = "Equall/Saul-7B-Instruct-v1"  # Default legal LLM
    HF_EMBEDDING_MODEL: str = "BAAI/bge-m3"  # Multilingual embeddings
    HF_USE_LOCAL: bool = False  # Use local models (requires GPU) vs Inference API
    HF_DEVICE: str = "cpu"  # cpu, cuda, or mps (for Apple Silicon)

    # Embedding Configuration
    EMBEDDING_PROVIDER: str = "hybrid"  # "openai", "huggingface", or "hybrid"
    # hybrid: Use HF for EU content (multilingual), OpenAI for general queries

    # Google (optional)
    GOOGLE_API_KEY: str | None = None
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_APPLICATION_CREDENTIALS: str | None = None  # Path to service account JSON for Translation API

    # LinkedIn (optional)
    LINKEDIN_CLIENT_ID: str | None = None
    LINKEDIN_CLIENT_SECRET: str | None = None

    # Stripe Payment Configuration
    STRIPE_PUBLISHABLE_KEY: str
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str | None = None  # Will be set when webhook is configured
    APP_URL: str = "http://localhost:5173"

    # Old tier prices (kept for migration, will be removed)
    STRIPE_YELLOW_MONTHLY_PRICE_ID: str | None = None
    STRIPE_YELLOW_ANNUAL_PRICE_ID: str | None = None
    STRIPE_BLUE_MONTHLY_PRICE_ID: str | None = None

    # Individual modules - Monthly
    STRIPE_CHAT_MONTHLY_PRICE_ID: str | None = None
    STRIPE_BUBBLE_MONTHLY_PRICE_ID: str | None = None
    STRIPE_AMENDATOR_MONTHLY_PRICE_ID: str | None = None
    STRIPE_COMPLY_MONTHLY_PRICE_ID: str | None = None
    STRIPE_TENDERATOR_MONTHLY_PRICE_ID: str | None = None

    # Individual modules - Annual
    STRIPE_CHAT_ANNUAL_PRICE_ID: str | None = None
    STRIPE_BUBBLE_ANNUAL_PRICE_ID: str | None = None
    STRIPE_AMENDATOR_ANNUAL_PRICE_ID: str | None = None
    STRIPE_COMPLY_ANNUAL_PRICE_ID: str | None = None
    STRIPE_TENDERATOR_ANNUAL_PRICE_ID: str | None = None

    # Bundles - Monthly
    STRIPE_STARTER_MONTHLY_PRICE_ID: str | None = None
    STRIPE_ADVOCATE_MONTHLY_PRICE_ID: str | None = None
    STRIPE_PROFESSIONAL_MONTHLY_PRICE_ID: str | None = None

    # Bundles - Annual
    STRIPE_STARTER_ANNUAL_PRICE_ID: str | None = None
    STRIPE_ADVOCATE_ANNUAL_PRICE_ID: str | None = None
    STRIPE_PROFESSIONAL_ANNUAL_PRICE_ID: str | None = None

    # EP Plan (APAs/MEPs)
    STRIPE_EP_MONTHLY_PRICE_ID: str | None = None
    STRIPE_EP_ANNUAL_PRICE_ID: str | None = None

    # Email (Gmail SMTP via Google Workspace)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None  # hello@beresol.eu
    SMTP_PASSWORD: str | None = None  # App Password from Google Workspace
    SMTP_FROM_NAME: str = "Brubru by Beresol"

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Scraper Configuration
    SCRAPER_USER_AGENT: str = "Brubru/1.0"
    SCRAPER_RATE_LIMIT_DELAY: float = 1.5
    SCRAPER_CACHE_TTL: int = 3600

    # Tavily Search API (Real-time web search for AI)
    TAVILY_API_KEY: str | None = None
    TAVILY_ENABLED: bool = True  # Enable/disable Tavily web search
    TAVILY_MAX_RESULTS: int = 5  # Max results per search
    TAVILY_SEARCH_DEPTH: str = "basic"  # "basic" or "advanced"

    # Tenderator Configuration (Phase 7-10)
    TENDERATOR_ENABLED: bool = True
    TENDERATOR_TED_API_URL: str = "https://api.ted.europa.eu/v3"
    TENDERATOR_TED_API_KEY: str | None = None  # TED API key (UUID without hyphens) from developer.ted.europa.eu
    TENDERATOR_TED_SPARQL_URL: str = "https://data.europa.eu/sparql"
    TENDERATOR_FETCH_INTERVAL_HOURS: int = 6  # How often to fetch new tenders
    TENDERATOR_MATCHING_INTERVAL_HOURS: int = 1  # How often to run matching
    TENDERATOR_MAX_TENDER_AGE_DAYS: int = 180  # Keep tenders for 6 months
    TENDERATOR_DEFAULT_PAGE_SIZE: int = 20
    TENDERATOR_MAX_MATCHES_PER_USER: int = 100  # Max active matches per user
    TENDERATOR_SME_VALUE_THRESHOLD: float = 5000000.0  # Max value for SME filter (5M EUR)

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into list"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]


# Global settings instance
settings = Settings()
