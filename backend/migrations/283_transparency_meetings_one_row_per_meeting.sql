-- 283: one row, and one stable id, per Commission Transparency Register meeting.
--
-- GovClipping (8 Oct 2026): "BruBru gives each transparency meeting a new UUID on every
-- reload". Confirmed. scripts/ingest_transparency_meetings.py minted uuid4() for every
-- row it read and inserted with a bare ON CONFLICT DO NOTHING, but the table's only
-- unique key was that random id, so nothing ever conflicted: each scheduled run
-- re-inserted every meeting. 475,782 rows held 30,155 meetings; 24,533 had copies
-- (median 19, up to 46 inserted on 12 different days), each served with its own id.
--
-- Identity: the register publishes no meeting id, so a meeting is one row of its table,
-- keyed by everything the row says (host, cabinet member, date, organisation, subject,
-- location, representatives). 29 meetings differ only in location or representatives
-- and are listed side by side in the register, so a smaller key would merge real rows.
-- meeting_key is GENERATED (immutable parts only: the date as a day number), so no
-- writer can forget it. The OLDEST copy of each meeting survives: its id is the one a
-- client saw first. Backup + duplicate->canonical id map:
-- backend/data/backups/transparency_meetings_*_2026-10-08*.csv.gz.
BEGIN;

LOCK TABLE transparency_meetings IN SHARE ROW EXCLUSIVE MODE;  -- no insert mid-migration

ALTER TABLE transparency_meetings
    ADD COLUMN IF NOT EXISTS meeting_key text GENERATED ALWAYS AS (
        md5(host_uuid || '|' || coalesce(host_name, '') || '|'
            || (meeting_date - DATE '2000-01-01')::text || '|'
            || organisation_met || '|' || subject || '|'
            || coalesce(location, '') || '|' || coalesce(representatives, ''))
    ) STORED;

DELETE FROM transparency_meetings t
USING (
    SELECT id, row_number() OVER (PARTITION BY meeting_key ORDER BY first_seen, id) AS rn
    FROM transparency_meetings
) d
WHERE t.id = d.id AND d.rn > 1;

CREATE UNIQUE INDEX IF NOT EXISTS ux_transparency_meetings_meeting_key
    ON transparency_meetings (meeting_key);

COMMENT ON COLUMN transparency_meetings.meeting_key IS
    'Identity of a meeting: md5 of the register row''s content. Unique; the ingest upserts on it, so a meeting keeps its first id.';

COMMIT;
