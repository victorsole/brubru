-- Migration 041: Archive feature for items with lifespan
--
-- Rationale: Items in My EU Bubble (tracked files, calendar events, consultations,
-- committee work, adopted texts, votes) accumulate over time. Once a procedure is
-- adopted, a consultation closes, or an event is past, the item should fade from
-- the active view but remain searchable. Users may also want to archive items
-- proactively (e.g. files they no longer follow).
--
-- Approach:
--   1. Add `archived_at TIMESTAMPTZ NULL` to every user_*_tracks table.
--      `NULL` = active (default). Non-null = archived at that moment.
--      Auto-archive jobs and user "Dismiss" actions both write here.
--   2. Add `archived_reason TEXT NULL` -- 'auto:adopted', 'auto:past', 'user', etc.
--   3. New `user_calendar_event_archives` table for archiving calendar items
--      (events themselves are shared; user-specific archive is a join table).
--   4. Indexes on `(user_id, archived_at)` to filter active vs archived fast.
--
-- Auto-archive cadence (handled by scheduled job, not this migration):
--   - user_carriage_tracks: when legislative_carriages.current_status IN
--     ('ADOPTED','PUBLISHED','REJECTED','LAPSED','WITHDRAWN') AND > 90 days old
--   - user_consultation_tracks: when consultation deadline_date < NOW() - 30 days
--   - user_calendar_event_archives: implicit -- events past today filter at query time
--   - user_text_adopted_tracks + user_vote_tracks: never auto-archive (user-curated)
--   - user_commission_doc_tracks + user_committee_work_tracks: when last_updated
--     > 180 days AND status = 'final' or 'adopted'

BEGIN;

-- 1. Add archive columns to all user_*_tracks tables
ALTER TABLE user_carriage_tracks
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS archived_reason TEXT;

ALTER TABLE user_commission_doc_tracks
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS archived_reason TEXT;

ALTER TABLE user_consultation_tracks
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS archived_reason TEXT;

ALTER TABLE user_committee_work_tracks
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS archived_reason TEXT;

ALTER TABLE user_text_adopted_tracks
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS archived_reason TEXT;

ALTER TABLE user_vote_tracks
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS archived_reason TEXT;

-- 2. Indexes for fast filtering of active vs archived
CREATE INDEX IF NOT EXISTS idx_user_carriage_tracks_active
    ON user_carriage_tracks(user_id, archived_at);
CREATE INDEX IF NOT EXISTS idx_user_commission_doc_tracks_active
    ON user_commission_doc_tracks(user_id, archived_at);
CREATE INDEX IF NOT EXISTS idx_user_consultation_tracks_active
    ON user_consultation_tracks(user_id, archived_at);
CREATE INDEX IF NOT EXISTS idx_user_committee_work_tracks_active
    ON user_committee_work_tracks(user_id, archived_at);
CREATE INDEX IF NOT EXISTS idx_user_text_adopted_tracks_active
    ON user_text_adopted_tracks(user_id, archived_at);
CREATE INDEX IF NOT EXISTS idx_user_vote_tracks_active
    ON user_vote_tracks(user_id, archived_at);

-- 3. New join table: user-specific archives of shared calendar events
CREATE TABLE IF NOT EXISTS user_calendar_event_archives (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    event_id UUID NOT NULL REFERENCES eu_calendar_events(id) ON DELETE CASCADE,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_reason TEXT NOT NULL DEFAULT 'user',
    UNIQUE(user_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_user_calendar_event_archives_user
    ON user_calendar_event_archives(user_id, archived_at DESC);

-- 4. Enable RLS on new table (per CLAUDE.md "Every new public.* table must have RLS")
ALTER TABLE user_calendar_event_archives ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_calendar_event_archives_owner_select
    ON user_calendar_event_archives FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY user_calendar_event_archives_owner_insert
    ON user_calendar_event_archives FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY user_calendar_event_archives_owner_delete
    ON user_calendar_event_archives FOR DELETE
    USING (user_id = auth.uid());

-- 5. View helper for "active items per user across My EU Bubble"
CREATE OR REPLACE VIEW v_user_active_track_counts AS
SELECT
    user_id,
    COUNT(*) FILTER (WHERE archived_at IS NULL) AS active_carriage_tracks,
    COUNT(*) FILTER (WHERE archived_at IS NOT NULL) AS archived_carriage_tracks
FROM user_carriage_tracks
GROUP BY user_id;

COMMIT;

-- Down migration (rollback):
-- BEGIN;
-- DROP VIEW IF EXISTS v_user_active_track_counts;
-- DROP TABLE IF EXISTS user_calendar_event_archives;
-- ALTER TABLE user_vote_tracks DROP COLUMN IF EXISTS archived_at, DROP COLUMN IF EXISTS archived_reason;
-- ALTER TABLE user_text_adopted_tracks DROP COLUMN IF EXISTS archived_at, DROP COLUMN IF EXISTS archived_reason;
-- ALTER TABLE user_committee_work_tracks DROP COLUMN IF EXISTS archived_at, DROP COLUMN IF EXISTS archived_reason;
-- ALTER TABLE user_consultation_tracks DROP COLUMN IF EXISTS archived_at, DROP COLUMN IF EXISTS archived_reason;
-- ALTER TABLE user_commission_doc_tracks DROP COLUMN IF EXISTS archived_at, DROP COLUMN IF EXISTS archived_reason;
-- ALTER TABLE user_carriage_tracks DROP COLUMN IF EXISTS archived_at, DROP COLUMN IF EXISTS archived_reason;
-- COMMIT;
