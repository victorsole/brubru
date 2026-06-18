-- Migration 148: Dormant prospect profiles + magic claim flow.
--
-- Lets us pre-provision a fully populated Brubru profile for a prospect
-- BEFORE we know their email, then hand them a single-use claim link
-- (Off the Radar Brussels 23 Jun 2026, future prospect campaigns).
--
-- Flow:
--   1. INSERT a row with linkedin_url + claim_token + claim_token_expires_at,
--      email NULL, password_hash NULL, pre_provisioned_at = now().
--   2. Attach private guide + MEUB filter state to the row exactly as
--      /private-guide skill Step 4b does for emailed prospects.
--   3. Share https://brubru.beresol.eu/claim/<token> via LinkedIn DM.
--   4. On first OAuth (Google/LinkedIn) or password setup, the backend
--      merges the OAuth identity onto the dormant row + sets claimed_at.
--
-- Brubru-wide Data API grants pattern: grants are NOT applied here because
-- the users table is service_role-only (no direct anon/authenticated read).
-- Per CLAUDE.md hard rule: every new public.* table needs explicit grants,
-- but this migration only adds columns to an existing table — existing
-- grants stay in place.

BEGIN;

-- 1. Relax email NOT NULL so dormant rows can exist without an email.
--    PostgreSQL treats NULL as distinct in UNIQUE constraints, so multiple
--    dormant rows coexist; on claim, email becomes set + remains unique.
ALTER TABLE users ALTER COLUMN email DROP NOT NULL;

-- 2. New columns.
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS linkedin_url TEXT,
    ADD COLUMN IF NOT EXISTS claim_token TEXT,
    ADD COLUMN IF NOT EXISTS claim_token_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS pre_provisioned_at TIMESTAMPTZ;

COMMENT ON COLUMN users.linkedin_url IS
    'Public LinkedIn profile URL captured at pre-provisioning. Stable identity anchor when email is unknown.';
COMMENT ON COLUMN users.claim_token IS
    'Single-use 32-byte urlsafe token included in the magic claim link. NULL after claimed_at is set.';
COMMENT ON COLUMN users.claim_token_expires_at IS
    'After this point GET /api/auth/claim/{token} returns 410 Gone. Default 30 days from pre_provisioned_at.';
COMMENT ON COLUMN users.claimed_at IS
    'First successful OAuth or password-setup completion. NULL = still dormant.';
COMMENT ON COLUMN users.pre_provisioned_at IS
    'When the dormant row was created. Drives the 30-day expiry computation.';

-- 3. Indexes / unique constraints (partial, NULL-friendly).
CREATE UNIQUE INDEX IF NOT EXISTS users_claim_token_uq
    ON users(claim_token) WHERE claim_token IS NOT NULL;
CREATE INDEX IF NOT EXISTS users_linkedin_url_idx
    ON users(linkedin_url) WHERE linkedin_url IS NOT NULL;
CREATE INDEX IF NOT EXISTS users_dormant_idx
    ON users(pre_provisioned_at) WHERE claimed_at IS NULL;

COMMIT;
