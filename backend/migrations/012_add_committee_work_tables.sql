-- Migration 012: Add EP Committee Work In Progress Tables
-- Created: January 30, 2026
--
-- This migration creates tables for tracking EP Committee "Work in Progress" items:
-- - committee_work_items: Main table for work items scraped from EP committees
-- - user_committee_work_tracks: User subscriptions to track work items
-- - committee_work_status_history: Historical status changes

-- Create enum types first
DO $$ BEGIN
    CREATE TYPE procedure_type_enum AS ENUM ('COD', 'APP', 'CNS', 'NLE', 'INI');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE committee_role_enum AS ENUM ('lead', 'associated', 'opinion');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE committee_work_status_enum AS ENUM (
        'in_committee', 'awaiting_vote', 'tabled', 'adopted',
        'rejected', 'withdrawn', 'pending', 'completed', 'unknown'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Committee Work Items table
CREATE TABLE IF NOT EXISTS committee_work_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identifiers
    procedure_ref VARCHAR NOT NULL,              -- OEIL ref: "2025/0580(CNS)"
    committee_code VARCHAR(10) NOT NULL,         -- e.g., "AFET", "LIBE"

    -- Content
    title VARCHAR NOT NULL,
    description TEXT,
    full_description TEXT,

    -- Procedure metadata
    procedure_type procedure_type_enum NOT NULL DEFAULT 'INI',
    committee_role committee_role_enum NOT NULL DEFAULT 'lead',

    -- Calculated relevance score (40-100 based on procedure_type)
    relevance_score INTEGER DEFAULT 40,

    -- Rapporteur
    rapporteur_name VARCHAR,
    rapporteur_mep_id VARCHAR,
    shadow_rapporteurs JSONB DEFAULT '[]'::jsonb,

    -- Status
    status committee_work_status_enum DEFAULT 'unknown',
    status_text VARCHAR,                         -- Original status text
    stage VARCHAR,                               -- Committee stage

    -- Timeline events
    timeline_events JSONB DEFAULT '[]'::jsonb,
    vote_date TIMESTAMP,
    vote_result VARCHAR,

    -- Related documents
    related_documents JSONB DEFAULT '[]'::jsonb,
    celex_numbers VARCHAR[] DEFAULT '{}',

    -- Cross-references to legislative_carriages
    legislative_carriage_id UUID REFERENCES legislative_carriages(id) ON DELETE SET NULL,

    -- URLs
    oeil_url VARCHAR,
    eurlex_url VARCHAR,
    ep_page_url VARCHAR,
    source_url VARCHAR,

    -- Temporal data
    scraped_at TIMESTAMP DEFAULT NOW(),
    first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Unique constraint on (procedure_ref, committee_code)
    CONSTRAINT uq_committee_work_procedure_committee UNIQUE (procedure_ref, committee_code)
);

-- Create indexes for committee_work_items
CREATE INDEX IF NOT EXISTS ix_committee_work_procedure_ref ON committee_work_items(procedure_ref);
CREATE INDEX IF NOT EXISTS ix_committee_work_committee_code ON committee_work_items(committee_code);
CREATE INDEX IF NOT EXISTS ix_committee_work_procedure_type ON committee_work_items(procedure_type);
CREATE INDEX IF NOT EXISTS ix_committee_work_status ON committee_work_items(status);
CREATE INDEX IF NOT EXISTS ix_committee_work_last_updated ON committee_work_items(last_updated);
CREATE INDEX IF NOT EXISTS ix_committee_work_legislative_carriage_id ON committee_work_items(legislative_carriage_id);

-- User Committee Work Tracks table
CREATE TABLE IF NOT EXISTS user_committee_work_tracks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    work_item_id UUID NOT NULL REFERENCES committee_work_items(id) ON DELETE CASCADE,

    -- Notification preferences
    notify_on_status_change BOOLEAN DEFAULT TRUE,
    notify_on_rapporteur_change BOOLEAN DEFAULT TRUE,
    notify_on_new_documents BOOLEAN DEFAULT TRUE,

    -- Tracking metadata
    tracked_since TIMESTAMP NOT NULL DEFAULT NOW(),
    last_notified_at TIMESTAMP,

    -- User notes
    notes TEXT,

    -- Unique constraint: user can only track each work item once
    CONSTRAINT uq_user_committee_work_track UNIQUE (user_id, work_item_id)
);

-- Create indexes for user_committee_work_tracks
CREATE INDEX IF NOT EXISTS ix_user_committee_work_track_user_id ON user_committee_work_tracks(user_id);
CREATE INDEX IF NOT EXISTS ix_user_committee_work_track_work_item_id ON user_committee_work_tracks(work_item_id);

-- Committee Work Status History table
CREATE TABLE IF NOT EXISTS committee_work_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id UUID NOT NULL REFERENCES committee_work_items(id) ON DELETE CASCADE,

    old_status committee_work_status_enum,
    new_status committee_work_status_enum NOT NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Additional context
    notes TEXT,
    detected_during_sync BOOLEAN DEFAULT TRUE
);

-- Create indexes for committee_work_status_history
CREATE INDEX IF NOT EXISTS ix_committee_work_status_history_work_item ON committee_work_status_history(work_item_id);
CREATE INDEX IF NOT EXISTS ix_committee_work_status_history_changed_at ON committee_work_status_history(changed_at);

-- Add comment to tables
COMMENT ON TABLE committee_work_items IS 'EP Committee Work in Progress items scraped from committee pages';
COMMENT ON TABLE user_committee_work_tracks IS 'User subscriptions to track specific committee work items';
COMMENT ON TABLE committee_work_status_history IS 'Historical status changes for committee work items';

-- Grant permissions (adjust as needed for your setup)
-- GRANT ALL PRIVILEGES ON TABLE committee_work_items TO brubru_app;
-- GRANT ALL PRIVILEGES ON TABLE user_committee_work_tracks TO brubru_app;
-- GRANT ALL PRIVILEGES ON TABLE committee_work_status_history TO brubru_app;
