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
    # Chat generation runs on a stacked chain of FREE open-model tiers (10 June
    # 2026 migration, see memory/project_chat_oss_migration.md). Order:
    # Groq (open, primary) -> Gemini (free) -> Mistral (free, EU) -> Cerebras
    # (open, deep fallback) -> Anthropic (opportunistic, when funded) -> OpenAI.
    GROQ_API_KEY: str | None = None  # Groq free tier (open models: Llama/Qwen/gpt-oss) — chat primary
    # llama-3.3-70b-versatile was decommissioned by Groq on 16 Aug 2026. Groq
    # recommended gpt-oss-120b or qwen3.6-27b; qwen wins on the axis that
    # matters here -- 5/5 correct EU act numbers with zero fabrications, where
    # both llama-3.3-70b and gpt-oss-120b invented 2 of 5 (including the AI
    # Act). It also keeps model diversity: Cerebras already runs gpt-oss-120b.
    # qwen emits <think> blocks, stripped by _strip_think / the stream suppressor.
    GROQ_MODEL: str = "qwen/qwen3.6-27b"
    CEREBRAS_API_KEY: str | None = None  # Cerebras free tier (gpt-oss-120b, zai-glm-4.7) — deep open fallback
    CEREBRAS_MODEL: str = "gpt-oss-120b"  # high TPD; reasoning model (reasoning_effort=low, content/<think> handled)
    NVIDIA_API_KEY: str | None = None  # NVIDIA NIM free tier (Llama-3.3-70B, 128K ctx) — 2nd open fallback below Cerebras
    NVIDIA_MODEL: str = "meta/llama-3.3-70b-instruct"  # permanent free; fits the ~19K-token Brubru prompt
    # Scaleway Generative APIs -- EU-hosted (Paris), OpenAI-compatible, paid but
    # cheap. Introduced 11 September 2026 as the reliable lane beneath the two
    # free fast ones, after a morning on which every provider in the chain failed
    # a single request: Cerebras and Gemini 429, Groq structurally (below),
    # NVIDIA 410 EOL, Mistral 429, OpenAI out of credits.
    #
    # Auth is the IAM secret key as a bearer token; SCW_SECRET_KEY is already in
    # .env for the Scaleway CLI, so no new credential was minted.
    #
    # Model chosen by measurement on the path users actually hit (11 Sep 2026).
    #
    # THE FIRST ANSWER WAS WRONG, AND THE WAY IT WAS WRONG IS THE POINT.
    # Scored on accuracy alone, deepseek-v4-flash-0731 won: 5/5 EU act numbers
    # and 4/4 needles in a 21K-token context. It is unusable here. On Scaleway
    # it is a REASONING model that emits its chain of thought into the `reasoning`
    # delta and only then produces content, and at max_tokens=1200 it never got
    # there: 339 reasoning deltas, ZERO content deltas, 43.9 seconds.
    # qwen3.5-397b-a17b does the same (1,200 reasoning deltas, zero content).
    #
    # generate_stream() deliberately refuses to stream reasoning deltas, because
    # doing so renders raw chain-of-thought into the user's chat window. So a
    # reasoning-only model yields nothing and falls through every single time.
    # Picking on accuracy would have wired in a provider that is dead on
    # /api/chat/stream, which is the only path the UI calls.
    #
    # Rescored over the STREAM-CAPABLE models only, two runs each:
    #
    #   model                          acts     needles@21K  1st token  stream
    #   qwen3-235b-a22b-instruct-2507  4,4 /5   4,4 /4       0.8s       clean     <- chosen
    #   gemma-4-26b-a4b-it             5,4 /5   4,4 /4       7.8s       971 reasoning deltas
    #   llama-3.3-70b-instruct         2,2 /5   4,4 /4       0.2s       clean, fabricated 3 numbers
    #   mistral-medium-3.5-128b        2,2 /5   4,4 /4       0.2s       clean, fabricated 1
    #
    # qwen wins on the axis that has always decided this: it does not invent act
    # numbers (one fabrication across two runs, against three for llama), it
    # reads the whole injected context, and being an *instruct* variant it cannot
    # regress into reasoning-only output the way the two rejects did. gemma edged
    # it once on acts but streams reasoning and takes ten times longer to the
    # first token.
    #
    # Note on provenance: the weights are Alibaba's Qwen, the hosting is
    # Scaleway's in the EU. That satisfies EU hosting, not EU model provenance.
    SCW_SECRET_KEY: str | None = None
    SCALEWAY_MODEL: str = "qwen3-235b-a22b-instruct-2507"
    MISTRAL_API_KEY: str | None = None  # Mistral (free tier, EU, open-weight) — fallback
    ANTHROPIC_API_KEY: str  # Claude (opportunistic — used only when free chain exhausted AND funded)
    OPENAI_API_KEY: str  # GPT-4 (paid last resort)
    OPENAI_ORG_ID: str | None = None
    GOOGLE_GEMINI_API_KEY: str | None = None  # Gemini 2.0 Flash (free, 1M ctx) — big-context catcher

    # OpenRouter — BATCH / EVALUATION ONLY, deliberately NOT in the chat chain.
    # One key fronts 341 models (OpenAI-compatible, so no new SDK). Benchmarked
    # 28 July 2026 at Brubru's real ~17K-token prompt; it is unfit for Chat:
    #   - free tier is capped at 50 requests/DAY (X-RateLimit-Limit: 50);
    #     $10 of credits raises it to 1,000/day, still short of chat volume
    #   - best free model ran 9.1s median vs Cerebras at 1.5s (6x slower)
    #   - paid models 402 below ~13K prompt tokens until credits are funded
    # Where it IS the right tool: offline batch work (translation, canon, KB
    # enrichment) where latency does not matter, and as an INDEPENDENT second
    # model for grading Brubru's own answers in /audit-queries and /training.
    # Enable explicitly per call site — never wire it into the chat fallback.
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL: str = "nvidia/nemotron-3-super-120b-a12b:free"  # 6/6 on the eval suite, 9.1s median
    OPENROUTER_SITE_URL: str = "https://brubru.beresol.eu"  # OpenRouter attribution headers
    OPENROUTER_APP_NAME: str = "Brubru"

    # Beresol Monitor API (partner policy-intelligence feeds, MEUB 4.2 Beresol Monitors)
    BERESOL_API_KEY: str | None = None
    BERESOL_API_BASE: str = "https://beresol.eu/api/v1"

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
    STRIPE_WEBHOOK_SECRET: str | None = None  # Subscriptions webhook (/api/stripe/webhook)
    STRIPE_BILLING_WEBHOOK_SECRET: str | None = None  # API-credits webhook (/api/billing/webhook) — Phase B (May 2026)
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
    # Operational alerts (e.g. MEUB feed went stale). Falls back to SMTP_USER.
    ALERT_EMAIL: str | None = None

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
