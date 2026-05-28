-- Migration 089: add audience column to daily_briefs for tenant-scoped chat cards.
--
-- Driver: EFPIA pilot (28 May 2026 to 28 June 2026) needs their own daily brief
-- card in the chat surface, alongside the standard public Brubru daily news card.
-- Future-extensible: Aurubis, MWCapital, Connect Europe, Danish PermRep, etc.
--
-- Semantics:
--   audience IS NULL                  -> public Brubru daily news (existing rows; unchanged)
--   audience = 'efpia'                -> only injected for EFPIA-resolved users
--   audience = '<tenant slug>'        -> only injected for users mapped to that slug
--
-- The chat-card injector and the EU CONTEXT builder filter on audience based on
-- the requesting user's email; see backend/data/audience_users.json.

ALTER TABLE daily_briefs
    ADD COLUMN IF NOT EXISTS audience VARCHAR(32) DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_daily_briefs_audience_date_priority
    ON daily_briefs (audience, brief_date DESC, priority DESC);

-- Supabase Data API grants (replay-safe per memory/feedback_supabase_data_api_grants.md).
-- daily_briefs is already publicly readable; restate the grants here so a fresh
-- environment spin-up does not lose access after the column add.
GRANT SELECT ON daily_briefs TO anon;
GRANT SELECT ON daily_briefs TO authenticated;
GRANT ALL    ON daily_briefs TO service_role;
