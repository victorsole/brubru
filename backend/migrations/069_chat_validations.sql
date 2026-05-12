-- 069 -- chat_validations table.
-- Backs services/ai/response_validator.py.
-- Workstream 1 of the Chat AI architecture evolution (see
-- memory/project_chat_ai_architecture_evolution.md).
--
-- Every chat response gets a Haiku-backed validator pass that checks the
-- response against the retrieved Brubru context blocks for hallucination,
-- completeness, and negation violations. First seven days run in shadow
-- mode (validator computes + logs but never modifies the shipped response).
--
-- Created: 12 May 2026.

CREATE TABLE IF NOT EXISTS chat_validations (
    id BIGSERIAL PRIMARY KEY,

    -- Truncated to 1000 chars at write time. Stored verbatim for debug.
    query TEXT NOT NULL,

    -- Truncated to 4000 chars at write time. The validator only sees the
    -- response after the post-processing pipeline (markdown stripping,
    -- linkification), so the excerpt reflects what the user got.
    response_excerpt TEXT NOT NULL,

    -- The model ID that ran the validation, e.g. claude-haiku-4-5-20251001.
    validator_model VARCHAR(64) NOT NULL,

    -- The provider that generated the response (Mistral, Anthropic, etc.).
    -- NULL when the generator identity is unknown.
    generator VARCHAR(64),

    -- Detected language of the query (2-letter ISO).
    language VARCHAR(8),

    -- Overall verdict.
    passed BOOLEAN NOT NULL,

    -- critical | warning | info.
    -- critical -> fabricated facts or "no data" claim when data is present.
    -- warning  -> completeness gap > 50% without "showing k of N" disclaimer.
    -- info     -> minor / no factual harm.
    severity VARCHAR(16) NOT NULL,

    -- Number of violations in the violations array.
    violation_count INTEGER NOT NULL DEFAULT 0,

    -- Array of {type, evidence, explanation} objects.
    -- type in (hallucination, completeness, negation).
    violations JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Validator end-to-end latency in milliseconds (Anthropic call + parsing).
    latency_ms INTEGER NOT NULL,

    -- Length of the context_str fed to the generator. Helpful for spotting
    -- whether truncation correlates with hallucination rate.
    context_length INTEGER,

    -- True while VALIDATOR_REGENERATE=false. The first seven days will all
    -- be shadow_mode=true. After we measure violation rates, the flag flips
    -- and subsequent rows show shadow_mode=false.
    shadow_mode BOOLEAN NOT NULL DEFAULT TRUE,

    -- Non-NULL when the validator itself failed (network error, JSON parse
    -- failure, etc.). passed defaults to TRUE in this case (fail-soft).
    error TEXT,

    -- Anonymous-friendly. NULL for pre-user / anonymous traffic.
    user_id UUID,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_chat_validations_created_at ON chat_validations(created_at DESC);
CREATE INDEX IF NOT EXISTS ix_chat_validations_passed ON chat_validations(passed);
CREATE INDEX IF NOT EXISTS ix_chat_validations_severity ON chat_validations(severity);
CREATE INDEX IF NOT EXISTS ix_chat_validations_generator ON chat_validations(generator);

-- RLS per learned rule (15 Apr 2026 PostgREST vulnerability fix).
-- This table is observability data, not user content. We allow service-role
-- read+write for the dashboard + analytics scripts.
ALTER TABLE chat_validations ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
    EXECUTE 'CREATE POLICY allow_read_chat_validations ON chat_validations FOR SELECT USING (true)';
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    EXECUTE 'CREATE POLICY allow_write_chat_validations ON chat_validations FOR INSERT WITH CHECK (true)';
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
