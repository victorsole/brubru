-- API Keys for the Brubru Data Provider API (/api/v1/*)
-- Professional subscribers can mint keys to call public paid endpoints
-- without consuming chatbot/AI credits.

CREATE TABLE IF NOT EXISTS api_keys (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash     CHAR(64) NOT NULL UNIQUE,
    key_prefix   VARCHAR(20) NOT NULL,
    name         VARCHAR(100) NOT NULL,
    scopes       JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_used_at TIMESTAMPTZ,
    last_used_ip INET,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_user_id
    ON api_keys (user_id);

CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash_active
    ON api_keys (key_hash)
    WHERE revoked_at IS NULL;
