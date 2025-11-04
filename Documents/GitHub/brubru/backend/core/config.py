"""
Application Configuration

Loads environment variables and provides typed configuration for the application.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "Brubru"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str

    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str  # Anon key (safe for frontend)
    SUPABASE_SERVICE_KEY: str  # Service role key (backend only)
    DATABASE_URL: str  # PostgreSQL connection string

    # AI Services
    ANTHROPIC_API_KEY: str
    OPENAI_API_KEY: str
    OPENAI_ORG_ID: str | None = None

    # Google (optional)
    GOOGLE_API_KEY: str | None = None
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    # LinkedIn (optional)
    LINKEDIN_CLIENT_ID: str | None = None
    LINKEDIN_CLIENT_SECRET: str | None = None

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Scraper Configuration
    SCRAPER_USER_AGENT: str = "Brubru/1.0"
    SCRAPER_RATE_LIMIT_DELAY: float = 1.5
    SCRAPER_CACHE_TTL: int = 3600

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into list"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
