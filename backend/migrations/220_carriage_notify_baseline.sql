-- 220: give tracked legislative files a notification baseline
--
-- WHY (audit, 25 August 2026)
--
-- Tracking is a promise of future notification, and Brubru has never once kept
-- it. Measured today:
--
--     user_carriage_tracks rows                     613
--     ...of which have last_notified_at set           0   <- ever, for anybody
--     notifications table, all time                 103   (all saved_search_alert)
--     most recent notification ever created  18 Jun 2026
--     ...of those 103, ever read                      0
--
-- The client case that surfaced it: a Terraqui lawyer on a paid trial tracked
-- 79 items, 56 of them legislative carriages, every one with
-- notify_on_status_change = TRUE. Forty-five of those files moved after
-- 11 August -- Green Claims completed, waste shipments completed, the Waste
-- Framework amendment tabled, ECHA close to adoption, all squarely in her
-- remit. She was told nothing, and stopped opening the product. Her behaviour
-- needs no other explanation.
--
-- Root cause, checked rather than assumed: services/notifications/
-- proactive_notifier.py builds Notification rows correctly but has NO CALLER
-- anywhere, does not import (it still reaches for `scrapers` and `anthropic`,
-- the latter removed from this codebase on 6 August), and contains zero
-- references to the tracking tables. api/cron.py schedules no notification job
-- at all. This was never a regression: the feature has never run.
--
-- WHY A NEW COLUMN
--
-- Detecting "the status changed since you last heard from us" needs an anchor.
-- The obvious one is legislative_carriages.status_history -- but that column is
-- EMPTY on all 2,770 rows, so nothing anywhere records when a status changed.
-- (Worth fixing in the carriages sweep separately; it is a third instrument
-- that records nothing.) last_updated is no good either: the nightly sweep
-- writes ~221 rows a day for reasons that are not status changes, so it would
-- notify constantly about nothing.
--
-- So the anchor is per-track and explicit: remember which status this user was
-- last told about. Two users who started tracking the same file at different
-- stages then get correct, independent notifications, and a status that flaps
-- back and forth cannot notify twice for the same value.
--
-- SEEDING
--
-- The column starts NULL, meaning "this user has never been told anything".
-- The notifier's first run MUST be invoked with --seed-baseline, which fills
-- the column from each carriage's current status WITHOUT notifying. Skipping
-- that step would fire 613 notifications in one go, most of them about changes
-- that happened before anyone was watching. The script refuses to send on a
-- track whose baseline is NULL for exactly this reason.

ALTER TABLE user_carriage_tracks
    ADD COLUMN IF NOT EXISTS last_notified_status TEXT;

COMMENT ON COLUMN user_carriage_tracks.last_notified_status IS
    'Carriage status this user was last notified about. NULL = never notified; '
    'the notifier seeds it without sending. Compared against '
    'legislative_carriages.current_status to detect a real change, because '
    'status_history is empty and last_updated bumps on every sweep write.';

-- Index the working set: active tracks that actually want status notifications.
-- The notifier scans this every run and it is the only query that touches the
-- new column.
CREATE INDEX IF NOT EXISTS idx_carriage_tracks_notify_active
    ON user_carriage_tracks (carriage_id, user_id)
    WHERE notify_on_status_change AND archived_at IS NULL;
