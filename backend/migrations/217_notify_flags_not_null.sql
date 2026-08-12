-- 217_notify_flags_not_null.sql
--
-- A single NULL notification flag returned HTTP 500 for a whole tab.
--
-- The notify_on_* columns on the tracking tables were nullable with no default,
-- while the API response model requires a boolean. One row inserted without the
-- flags therefore failed validation, and the handler turned that into a 500 for
-- every tracked item the user had: My Tracked Files rendered nothing at all.
--
-- Measured 12 August 2026: 15 of 249 committee-work tracks and 142 of 599
-- carriage tracks carried NULLs, affecting five accounts, two of them paying
-- subscribers. The rows were backfilled to TRUE, which is what the other 234
-- and 457 rows already used, and the columns can no longer accept NULL.
--
-- The API schema also defaults these fields now, so a stray NULL from any
-- future insert path degrades to the prevailing value instead of blanking a
-- page. Belt and braces, deliberately: this failure mode is silent until a user
-- opens the tab.

ALTER TABLE user_committee_work_tracks
    ALTER COLUMN notify_on_status_change     SET DEFAULT TRUE,
    ALTER COLUMN notify_on_rapporteur_change SET DEFAULT TRUE,
    ALTER COLUMN notify_on_new_documents     SET DEFAULT TRUE;

UPDATE user_committee_work_tracks SET
    notify_on_status_change     = COALESCE(notify_on_status_change, TRUE),
    notify_on_rapporteur_change = COALESCE(notify_on_rapporteur_change, TRUE),
    notify_on_new_documents     = COALESCE(notify_on_new_documents, TRUE);

ALTER TABLE user_committee_work_tracks
    ALTER COLUMN notify_on_status_change     SET NOT NULL,
    ALTER COLUMN notify_on_rapporteur_change SET NOT NULL,
    ALTER COLUMN notify_on_new_documents     SET NOT NULL;

ALTER TABLE user_carriage_tracks
    ALTER COLUMN notify_on_status_change SET DEFAULT TRUE,
    ALTER COLUMN notify_on_blocking      SET DEFAULT TRUE,
    ALTER COLUMN notify_on_new_documents SET DEFAULT TRUE;

UPDATE user_carriage_tracks SET
    notify_on_status_change = COALESCE(notify_on_status_change, TRUE),
    notify_on_blocking      = COALESCE(notify_on_blocking, TRUE),
    notify_on_new_documents = COALESCE(notify_on_new_documents, TRUE);

ALTER TABLE user_carriage_tracks
    ALTER COLUMN notify_on_status_change SET NOT NULL,
    ALTER COLUMN notify_on_blocking      SET NOT NULL,
    ALTER COLUMN notify_on_new_documents SET NOT NULL;
