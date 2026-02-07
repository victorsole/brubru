-- Migration 016: Add EP Texts Adopted Tables
-- Created: February 7, 2026
--
-- This migration creates tables for EP adopted texts (resolutions,
-- legislative resolutions, decisions, recommendations):
-- - texts_adopted: Main table for adopted texts scraped from EP
-- - user_text_adopted_tracks: User subscriptions to track adopted texts

-- Create enum type first (named adopted_text_type to avoid conflict with existing text_type_enum)
DO $$ BEGIN
    CREATE TYPE adopted_text_type AS ENUM (
        'resolution', 'legislative_resolution', 'decision',
        'recommendation', 'other'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Texts Adopted table
CREATE TABLE IF NOT EXISTS texts_adopted (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identifiers
    ta_reference VARCHAR NOT NULL UNIQUE,         -- e.g. "P10_TA(2025)0042"
    title VARCHAR NOT NULL,
    description TEXT,

    -- Classification
    text_type adopted_text_type NOT NULL DEFAULT 'other',
    procedure_ref VARCHAR,                        -- OEIL ref e.g. "2024/0176(COD)"
    parliamentary_term INTEGER NOT NULL DEFAULT 10,

    -- Content (from detail page enrichment)
    full_text TEXT,

    -- Temporal
    adoption_date TIMESTAMP NOT NULL,

    -- Metadata (from detail page enrichment)
    committees VARCHAR[] DEFAULT '{}',
    rapporteur_name VARCHAR,
    rapporteur_mep_id VARCHAR,
    celex_number VARCHAR,
    vote_results JSONB,                           -- {for, against, abstentions}
    related_documents JSONB DEFAULT '[]'::jsonb,  -- [{title, url, type}]

    -- URLs
    source_url VARCHAR,
    full_text_url VARCHAR,
    pdf_url VARCHAR,

    -- Cross-references to legislative_carriages
    legislative_carriage_id UUID REFERENCES legislative_carriages(id) ON DELETE SET NULL,

    -- Temporal data
    scraped_at TIMESTAMP DEFAULT NOW(),
    first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes for texts_adopted
CREATE INDEX IF NOT EXISTS ix_texts_adopted_ta_reference ON texts_adopted(ta_reference);
CREATE INDEX IF NOT EXISTS ix_texts_adopted_adoption_date ON texts_adopted(adoption_date);
CREATE INDEX IF NOT EXISTS ix_texts_adopted_procedure_ref ON texts_adopted(procedure_ref);
CREATE INDEX IF NOT EXISTS ix_texts_adopted_parliamentary_term ON texts_adopted(parliamentary_term);
CREATE INDEX IF NOT EXISTS ix_texts_adopted_text_type ON texts_adopted(text_type);
CREATE INDEX IF NOT EXISTS ix_texts_adopted_legislative_carriage_id ON texts_adopted(legislative_carriage_id);

-- User Text Adopted Tracks table
CREATE TABLE IF NOT EXISTS user_text_adopted_tracks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text_adopted_id UUID NOT NULL REFERENCES texts_adopted(id) ON DELETE CASCADE,

    -- Tracking metadata
    tracked_since TIMESTAMP NOT NULL DEFAULT NOW(),
    notes TEXT,

    -- Unique constraint: user can only track each text once
    CONSTRAINT uq_user_text_adopted_track UNIQUE (user_id, text_adopted_id)
);

-- Create indexes for user_text_adopted_tracks
CREATE INDEX IF NOT EXISTS ix_user_text_adopted_track_user_id ON user_text_adopted_tracks(user_id);
CREATE INDEX IF NOT EXISTS ix_user_text_adopted_track_text_adopted_id ON user_text_adopted_tracks(text_adopted_id);

-- Add comments
COMMENT ON TABLE texts_adopted IS 'EP adopted texts (resolutions, legislative resolutions, decisions) scraped from EP plenary';
COMMENT ON TABLE user_text_adopted_tracks IS 'User subscriptions to track specific adopted texts';
