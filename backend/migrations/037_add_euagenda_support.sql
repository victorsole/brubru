-- Migration 037: euagenda.eu integration for EU Calendar
-- Adds THIRD_PARTY institution, 5 new event types, and organiser/venue columns
-- to support events from https://euagenda.eu/ (think tanks, conferences,
-- webinars, training, associations).
--
-- Enum type names are snake_case in this schema: institution_enum, event_type_enum.
-- ALTER TYPE ADD VALUE cannot run inside a transaction in PostgreSQL, so
-- statements are top-level (no BEGIN/COMMIT). Idempotent via IF NOT EXISTS.

-- 1. InstitutionEnum: add THIRD_PARTY for non-EU-institutional sources
ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'THIRD_PARTY';

-- 2. EventTypeEnum: add new event types for third-party events
ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS 'conference';
ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS 'webinar';
ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS 'roundtable';
ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS 'training';
ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS 'workshop';

-- 3. Add organiser + venue columns
ALTER TABLE eu_calendar_events
    ADD COLUMN IF NOT EXISTS organiser TEXT,
    ADD COLUMN IF NOT EXISTS venue TEXT;

COMMENT ON COLUMN eu_calendar_events.organiser IS 'Organising body (think tank, conference organiser, public body) — used for THIRD_PARTY events primarily';
COMMENT ON COLUMN eu_calendar_events.venue IS 'Physical venue or "Online Webinar" — used for THIRD_PARTY events primarily';

-- 4. Index for source filtering
CREATE INDEX IF NOT EXISTS ix_eu_calendar_events_source_date ON eu_calendar_events (source, start_date DESC);
