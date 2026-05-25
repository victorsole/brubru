-- Migration 084 — Saved-search alert subscriptions
--
-- Lets a user save a phrase ("official languages of the Union",
-- "linguistic minorities", "Catalan OR Basque OR Galician") and have a
-- nightly job scan the EU corpus (eu_laws, texts_adopted,
-- legislative_carriages, scraped news) for new matches. New matches
-- become Notification rows via the existing notifications table, so
-- chat-greeting + the MEUB dashboard tile can surface them without a
-- second delivery system.
--
-- Reuses notifications.notification_type = 'saved_search_alert' for the
-- new rows. Each event row carries the originating subscription_id in
-- notif_metadata.subscription_id so the FE can group / filter.
--
-- Permission policy:
--   - anon: no access (per Supabase Data API hard rule)
--   - authenticated: SELECT/INSERT/UPDATE/DELETE OWN rows only (RLS)
--   - service_role: ALL (for the nightly runner running under the
--                    backend's service-role key)
--
-- Safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS user_alert_subscriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label           TEXT NOT NULL,
    query_phrase    TEXT NOT NULL,
    -- websearch_to_tsquery() format. NULL means runner derives it from query_phrase.
    query_tsquery   TEXT,
    -- Which corpora to scan. Subset of:
    --   eu_laws | texts_adopted | legislative_carriages | rss_entries |
    --   committee_documents | press_releases | college_agendas |
    --   council_agendas
    scopes          TEXT[] NOT NULL DEFAULT ARRAY['eu_laws','texts_adopted','legislative_carriages','rss_entries']::TEXT[],
    -- Delivery channels actually used by the runner.
    --   chat_greeting    -> surfaces on /api/personalization/greeting
    --   meub_tile        -> existing notifications-tile, badge counter
    --   email_weekly     -> Sunday digest send
    delivery        TEXT[] NOT NULL DEFAULT ARRAY['chat_greeting','meub_tile']::TEXT[],
    -- Optional: kill noise from a specific source.
    exclude_terms   TEXT[],
    -- Optional: language filter, e.g. ARRAY['en','fr'] to scan only EN/FR rows.
    language_codes  VARCHAR(8)[],
    -- Optional: priority override. NULL means the runner infers per match.
    priority_override VARCHAR(10) CHECK (priority_override IS NULL OR priority_override IN ('low','normal','high','urgent')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at     TIMESTAMPTZ,
    last_match_at   TIMESTAMPTZ,
    last_match_count INTEGER NOT NULL DEFAULT 0,
    -- Free-text notes the user wrote about why this alert matters.
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT user_alert_subscriptions_label_per_user UNIQUE (user_id, label)
);

CREATE INDEX IF NOT EXISTS ix_user_alert_subscriptions_user_active
    ON user_alert_subscriptions (user_id, is_active)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS ix_user_alert_subscriptions_last_run
    ON user_alert_subscriptions (last_run_at NULLS FIRST)
    WHERE is_active = TRUE;

-- RLS
ALTER TABLE user_alert_subscriptions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS alerts_own_select ON user_alert_subscriptions;
CREATE POLICY alerts_own_select ON user_alert_subscriptions
    FOR SELECT TO authenticated
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS alerts_own_insert ON user_alert_subscriptions;
CREATE POLICY alerts_own_insert ON user_alert_subscriptions
    FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS alerts_own_update ON user_alert_subscriptions;
CREATE POLICY alerts_own_update ON user_alert_subscriptions
    FOR UPDATE TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS alerts_own_delete ON user_alert_subscriptions;
CREATE POLICY alerts_own_delete ON user_alert_subscriptions
    FOR DELETE TO authenticated
    USING (user_id = auth.uid());

-- Data API grants (hard rule, set 15 May 2026)
REVOKE ALL ON user_alert_subscriptions FROM anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON user_alert_subscriptions TO authenticated;
GRANT ALL ON user_alert_subscriptions TO service_role;

-- Trigger to keep updated_at fresh.
CREATE OR REPLACE FUNCTION trg_user_alert_subscriptions_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS user_alert_subscriptions_touch_updated_at ON user_alert_subscriptions;
CREATE TRIGGER user_alert_subscriptions_touch_updated_at
    BEFORE UPDATE ON user_alert_subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION trg_user_alert_subscriptions_touch_updated_at();

COMMIT;
