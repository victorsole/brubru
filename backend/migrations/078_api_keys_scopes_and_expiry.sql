-- migrations/078_api_keys_scopes_and_expiry.sql
-- API vertical Phase A foundation (21 May 2026).
--
-- Adds the columns required by:
--   1. Scope-based authorisation (replaces the blanket subscription_tier='blue' gate).
--   2. Self-serve key minting with default 180-day expiry.
--   3. A single Brubru-funded sandbox key for the public /api/docs "Try it"
--      experience and Postman public-collection examples.
--
-- Back-compat:
--   Existing rows currently have scopes='[]'::jsonb (the model default).
--   This migration backfills scopes='["*"]'::jsonb so every previously-minted
--   admin key (including GovClipping's) keeps blanket access. Self-serve keys
--   minted after this migration default to a narrower scope set chosen by the
--   user at mint time.
--
-- Per CLAUDE.md hard rule (Supabase Data API grants mandatory, 15 May 2026):
-- explicit grants are required for every public.* table touched. RLS already
-- enabled on api_keys; we only add column-level GRANTs here.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. New columns
-- ---------------------------------------------------------------------------

-- Optional expiry. NULL means "never expires" (admin-minted, back-compat).
-- Self-serve mint always sets this (default 180 days).
ALTER TABLE public.api_keys
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ NULL;

-- Sandbox flag. Exactly one row in production should have is_sandbox=TRUE;
-- that row's key powers the /api/docs Try-It buttons and is Brubru-funded
-- (debits against api_sandbox_pool, not against a user balance).
ALTER TABLE public.api_keys
    ADD COLUMN IF NOT EXISTS is_sandbox BOOLEAN NOT NULL DEFAULT FALSE;

-- ---------------------------------------------------------------------------
-- 2. Backfill scopes for existing rows
-- ---------------------------------------------------------------------------
-- Every previously-minted key has scopes='[]'::jsonb (model default before
-- this migration). Promote them all to ["*"] so blanket access is preserved.
-- Self-serve mints from now on choose their own scopes.

UPDATE public.api_keys
SET scopes = '["*"]'::jsonb
WHERE scopes = '[]'::jsonb
   OR scopes IS NULL;

-- ---------------------------------------------------------------------------
-- 3. Indexes
-- ---------------------------------------------------------------------------

-- Hot path: lookup by key_hash where the key is active and not expired.
-- key_hash is already unique-indexed; this composite partial index helps
-- the "list my active keys" / "is this key live?" queries.
CREATE INDEX IF NOT EXISTS idx_api_keys_user_active
    ON public.api_keys (user_id)
    WHERE revoked_at IS NULL;

-- Sole-sandbox lookup. Partial unique to enforce at most one sandbox key.
CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_single_sandbox
    ON public.api_keys (is_sandbox)
    WHERE is_sandbox = TRUE AND revoked_at IS NULL;

-- ---------------------------------------------------------------------------
-- 4. Constraint: name length
-- ---------------------------------------------------------------------------
-- Model already enforces String(100). Add a DB-level minimum so blank/junk
-- labels don't slip through if the mint path skips validation.
ALTER TABLE public.api_keys
    DROP CONSTRAINT IF EXISTS api_keys_name_length;
ALTER TABLE public.api_keys
    ADD CONSTRAINT api_keys_name_length
    CHECK (char_length(name) BETWEEN 1 AND 100);

-- ---------------------------------------------------------------------------
-- 5. Grants
-- ---------------------------------------------------------------------------
-- The api_keys table is accessed exclusively through the FastAPI service-role
-- connection (not via Supabase Data API), so anon/authenticated need nothing.
-- We still issue the explicit revoke + service_role grant per the hard rule.

REVOKE ALL ON public.api_keys FROM anon;
REVOKE ALL ON public.api_keys FROM authenticated;
GRANT ALL ON public.api_keys TO service_role;

COMMIT;
