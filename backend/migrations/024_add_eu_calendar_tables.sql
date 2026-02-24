-- Migration 024: Add EU Calendar tables
-- My EU Calendar feature: aggregates events from EU institutions
-- Created: February 2026

-- ============================================================================
-- ENUMS (with duplicate guards)
-- ============================================================================

DO $$ BEGIN
    CREATE TYPE institution_enum AS ENUM (
        'EP', 'COUNCIL', 'EUROPEAN_COUNCIL', 'COMMISSION',
        'ECJ', 'ECB', 'ESMA', 'EMA', 'EBA', 'EIOPA'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE event_type_enum AS ENUM (
        'plenary_session', 'committee_week', 'group_week', 'recess',
        'council_meeting', 'informal_meeting', 'european_council_summit',
        'eurogroup', 'commission_college_meeting', 'court_hearing',
        'ecb_governing_council', 'agency_event', 'special_date',
        'comitology_meeting', 'expert_group_meeting', 'grant_deadline'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE event_status_enum AS ENUM (
        'scheduled', 'confirmed', 'tentative',
        'cancelled', 'completed', 'postponed'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE reminder_period_enum AS ENUM ('1h', '1d', '1w');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================================
-- TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS eu_calendar_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Institution and type
    institution institution_enum NOT NULL,
    event_type event_type_enum NOT NULL,

    -- Content
    title VARCHAR NOT NULL,
    description TEXT,

    -- Date/time
    start_date DATE NOT NULL,
    end_date DATE,
    start_time TIME,
    end_time TIME,
    all_day BOOLEAN DEFAULT TRUE,

    -- Institution-specific metadata
    council_configuration VARCHAR,
    ep_activity_type VARCHAR,
    ep_committee_code VARCHAR,
    commission_dg VARCHAR,

    -- Classification
    policy_areas TEXT[] DEFAULT '{}',
    status event_status_enum DEFAULT 'scheduled',

    -- Links
    source_url VARCHAR,
    agenda_url VARCHAR,

    -- Legislative cross-references
    procedure_refs TEXT[] DEFAULT '{}',
    related_documents JSONB DEFAULT '{}',

    -- Source tracking
    source VARCHAR NOT NULL,
    external_id VARCHAR,

    -- Temporal
    scraped_at TIMESTAMP DEFAULT NOW(),
    first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Unique constraint on source data
    CONSTRAINT uq_calendar_source_external_id UNIQUE (source, external_id)
);

COMMENT ON TABLE eu_calendar_events IS 'EU institutional calendar events for My EU Calendar feature';

CREATE TABLE IF NOT EXISTS user_calendar_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Institution-level subscription
    institution institution_enum,
    council_configuration VARCHAR,
    ep_committee_code VARCHAR,
    commission_dg VARCHAR,
    notify_on_new BOOLEAN DEFAULT TRUE,

    -- Per-event reminder
    event_id UUID REFERENCES eu_calendar_events(id) ON DELETE CASCADE,
    remind_before reminder_period_enum,
    reminded_at TIMESTAMP,

    -- Temporal
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE user_calendar_subscriptions IS 'User subscriptions and reminders for EU Calendar events';

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS ix_calendar_start_date ON eu_calendar_events (start_date);
CREATE INDEX IF NOT EXISTS ix_calendar_institution ON eu_calendar_events (institution);
CREATE INDEX IF NOT EXISTS ix_calendar_event_type ON eu_calendar_events (event_type);
CREATE INDEX IF NOT EXISTS ix_calendar_last_updated ON eu_calendar_events (last_updated);

CREATE INDEX IF NOT EXISTS ix_cal_sub_user_id ON user_calendar_subscriptions (user_id);
CREATE INDEX IF NOT EXISTS ix_cal_sub_event_id ON user_calendar_subscriptions (event_id);
