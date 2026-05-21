-- Migration 082: Defensive DB-side defaults + NOT NULL + CHECK on three
-- more `users` columns whose ORM defaults are silently ignored by raw INSERT.
--
-- Same shape as migration 081 (which closed the door on users.role).
-- Flagged as 082 candidates in migration 081's commit message.
--
-- Columns covered:
--   - users.subscription_tier (ORM default 'white'; CHECK in 'white','yellow','blue')
--   - users.is_active (ORM default TRUE)
--   - users.is_verified (ORM default FALSE)
--
-- Background:
--   The User model declares these as Column(..., default=...). Those defaults
--   are ORM-side only. Any raw SQL INSERT path that omits the column lands
--   with NULL, which silently breaks downstream logic:
--     - subscription_tier=NULL: tier-gated endpoints (Predictions, Council
--       pack, AI quotas) treat the user as having an unrecognised tier and
--       500 their requests.
--     - is_active=NULL: middleware may evaluate falsy and lock the user out
--       silently.
--     - is_verified=NULL: email-verification gates 500 on the boolean check.
--
-- Pre-flight audit (verified 21 May 2026):
--   - subscription_tier: 44 'white', 22 'blue', 5 'yellow'. 0 NULL. 0 outside
--     allowlist.
--   - is_active: 0 NULL.
--   - is_verified: 0 NULL.

BEGIN;

-- subscription_tier ---------------------------------------------------------
ALTER TABLE public.users ALTER COLUMN subscription_tier SET DEFAULT 'white';
ALTER TABLE public.users ALTER COLUMN subscription_tier SET NOT NULL;
ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_subscription_tier_check;
ALTER TABLE public.users
    ADD CONSTRAINT users_subscription_tier_check
    CHECK (subscription_tier IN ('white', 'yellow', 'blue'));
COMMENT ON CONSTRAINT users_subscription_tier_check ON public.users IS 'Pins subscription_tier to the application allowlist (white, yellow, blue). See migration 082 and CLAUDE.md (Pricing Model section). Internal gating uses white/yellow/blue; user-facing plan names (Starter / Advocate / Professional / EP) are a separate translation layer.';

-- is_active -----------------------------------------------------------------
ALTER TABLE public.users ALTER COLUMN is_active SET DEFAULT TRUE;
ALTER TABLE public.users ALTER COLUMN is_active SET NOT NULL;

-- is_verified ---------------------------------------------------------------
ALTER TABLE public.users ALTER COLUMN is_verified SET DEFAULT FALSE;
ALTER TABLE public.users ALTER COLUMN is_verified SET NOT NULL;

COMMIT;
