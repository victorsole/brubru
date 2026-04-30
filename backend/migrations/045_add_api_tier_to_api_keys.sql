-- 045_add_api_tier_to_api_keys.sql
--
-- Per-key rate-limit tier. Default 'free' (60 req/min). 'pro' = 300 req/min.
-- 'enterprise' = 6000 req/min — used for partner integrations (GovClipping, etc.).
--
-- Enforced in services/rate_limiter/global_rate_limiter.py and
-- api/v1/_deps.api_user_with_rate_limit.

ALTER TABLE api_keys
    ADD COLUMN IF NOT EXISTS api_tier VARCHAR(20) NOT NULL DEFAULT 'free';

CREATE INDEX IF NOT EXISTS idx_api_keys_api_tier ON api_keys (api_tier);

COMMENT ON COLUMN api_keys.api_tier IS
    'Rate-limit tier for /api/v1 calls. free=60/min, pro=300/min, enterprise=6000/min.';
