-- migrations/079_api_billing.sql
-- API vertical Phase B — Anthropic-style euro billing (21 May 2026).
--
-- What this adds:
--   1. users.api_balance_eur_micro             -> per-user euro balance (BIGINT μEUR).
--      Default 0 — Brubru explicitly does NOT give free credit on signup
--      (sandbox key in api_sandbox_pool covers public evaluators).
--   2. users.api_auto_topup_*                  -> opt-in auto-top-up settings.
--   3. public.api_usage_events                 -> per-call debit ledger.
--   4. public.api_topup_events                 -> Stripe top-up ledger.
--   5. public.api_sandbox_pool                 -> daily-counter for the shared sandbox
--      key (global 100/day cap, 10/IP/day enforced in the application layer).
--
-- Money representation:
--   BIGINT micro-euros (μEUR), 6 decimal places. 1 EUR = 1_000_000.
--   Avoids float-drift on small per-call amounts (0.001 EUR = 1_000 μEUR).
--
-- Concurrency:
--   The atomic-debit pattern lives in services/billing/api_meter.py and uses
--   `UPDATE users SET api_balance_eur_micro = api_balance_eur_micro - $cost
--    WHERE id = $uid AND api_balance_eur_micro >= $cost RETURNING ...`
--   This is race-safe at READ COMMITTED isolation (Postgres default).
--
-- Refunds:
--   On a 5xx from a v1 route handler, the meter middleware refunds the cost
--   (`UPDATE users ... api_balance_eur_micro + $cost ... ; status='refunded'`).
--   4xx errors do not refund — the caller-side mistake still consumed work.
--
-- Per CLAUDE.md hard rule (Supabase Data API grants mandatory, 15 May 2026):
-- every new public.* table ships with RLS + explicit grants. Order:
-- CREATE TABLE -> ENABLE RLS -> CREATE POLICY -> GRANT.

BEGIN;

-- ===========================================================================
-- 1. users.api_balance_eur_micro + auto-top-up
-- ===========================================================================

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS api_balance_eur_micro BIGINT NOT NULL DEFAULT 0
        CHECK (api_balance_eur_micro >= 0);

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS api_auto_topup_enabled BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS api_auto_topup_threshold_micro BIGINT NULL
        CHECK (api_auto_topup_threshold_micro IS NULL OR api_auto_topup_threshold_micro >= 0);

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS api_auto_topup_amount_micro BIGINT NULL
        CHECK (api_auto_topup_amount_micro IS NULL OR api_auto_topup_amount_micro >= 1000000); -- min 1 EUR

-- ===========================================================================
-- 2. api_usage_events  (per-call debit ledger)
-- ===========================================================================

CREATE TABLE IF NOT EXISTS public.api_usage_events (
    id                  BIGSERIAL       PRIMARY KEY,
    user_id             UUID            NULL REFERENCES public.users(id) ON DELETE SET NULL,
    api_key_id          UUID            NULL REFERENCES public.api_keys(id) ON DELETE SET NULL,
    endpoint            TEXT            NOT NULL,
    method              TEXT            NOT NULL,
    cost_eur_micro      BIGINT          NOT NULL CHECK (cost_eur_micro >= 0),
    request_id          TEXT            NULL,
    status_code         INTEGER         NULL,
    is_sandbox          BOOLEAN         NOT NULL DEFAULT FALSE,
    refunded            BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_usage_user_created
    ON public.api_usage_events (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_api_usage_key_created
    ON public.api_usage_events (api_key_id, created_at DESC);

ALTER TABLE public.api_usage_events ENABLE ROW LEVEL SECURITY;

-- The backend uses service_role exclusively; we still ship a tight policy
-- for completeness.
DROP POLICY IF EXISTS api_usage_events_service_role ON public.api_usage_events;
CREATE POLICY api_usage_events_service_role
    ON public.api_usage_events
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

REVOKE ALL ON public.api_usage_events FROM anon;
REVOKE ALL ON public.api_usage_events FROM authenticated;
GRANT ALL ON public.api_usage_events TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.api_usage_events_id_seq TO service_role;

-- ===========================================================================
-- 3. api_topup_events  (Stripe top-up ledger)
-- ===========================================================================

CREATE TABLE IF NOT EXISTS public.api_topup_events (
    id                          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                     UUID            NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    amount_eur_micro            BIGINT          NOT NULL CHECK (amount_eur_micro >= 1000000), -- min 1 EUR
    stripe_payment_intent_id    TEXT            NOT NULL UNIQUE,
    status                      TEXT            NOT NULL DEFAULT 'pending'
                                                CHECK (status IN ('pending','succeeded','failed','refunded')),
    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    succeeded_at                TIMESTAMPTZ     NULL,
    failed_at                   TIMESTAMPTZ     NULL
);

CREATE INDEX IF NOT EXISTS idx_api_topup_user_created
    ON public.api_topup_events (user_id, created_at DESC);

ALTER TABLE public.api_topup_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS api_topup_events_service_role ON public.api_topup_events;
CREATE POLICY api_topup_events_service_role
    ON public.api_topup_events
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

REVOKE ALL ON public.api_topup_events FROM anon;
REVOKE ALL ON public.api_topup_events FROM authenticated;
GRANT ALL ON public.api_topup_events TO service_role;

-- ===========================================================================
-- 4. api_sandbox_pool  (daily counter for shared sandbox key)
-- ===========================================================================
-- One row per UTC date. Application reads + increments via INSERT...ON CONFLICT
-- to atomically advance the daily counter. When `count_total` >= 100 OR
-- (`ip_address`, `count_for_ip`) >= 10 for a given IP, the sandbox returns 429.

CREATE TABLE IF NOT EXISTS public.api_sandbox_pool (
    pool_date       DATE            NOT NULL,
    ip_address      INET            NOT NULL DEFAULT '0.0.0.0'::inet,
    count_today     INTEGER         NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (pool_date, ip_address)
);

-- Quick "global today" sum: SELECT SUM(count_today) FROM api_sandbox_pool WHERE pool_date = CURRENT_DATE
CREATE INDEX IF NOT EXISTS idx_api_sandbox_pool_date
    ON public.api_sandbox_pool (pool_date);

ALTER TABLE public.api_sandbox_pool ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS api_sandbox_pool_service_role ON public.api_sandbox_pool;
CREATE POLICY api_sandbox_pool_service_role
    ON public.api_sandbox_pool
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

REVOKE ALL ON public.api_sandbox_pool FROM anon;
REVOKE ALL ON public.api_sandbox_pool FROM authenticated;
GRANT ALL ON public.api_sandbox_pool TO service_role;

COMMIT;
