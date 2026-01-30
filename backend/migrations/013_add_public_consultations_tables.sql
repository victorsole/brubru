-- Migration: 013_add_public_consultations_tables
-- Description: Add tables for EC Public Consultations (Have Your Say portal)
-- Created: January 2026

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- Enum Types
-- ============================================================================

-- Consultation types
DO $$ BEGIN
    CREATE TYPE consultation_type_enum AS ENUM (
        'public_consultation',
        'call_for_evidence',
        'feedback',
        'roadmap',
        'initiative'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Consultation statuses
DO $$ BEGIN
    CREATE TYPE consultation_status_enum AS ENUM (
        'open',
        'upcoming',
        'closed',
        'outcome_published',
        'withdrawn'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Document types
DO $$ BEGIN
    CREATE TYPE consultation_document_type_enum AS ENUM (
        'questionnaire',
        'impact_assessment',
        'draft_act',
        'explanatory_memo',
        'annex',
        'factsheet',
        'summary',
        'inception_impact_assessment',
        'roadmap',
        'outcome_report',
        'statistics',
        'other'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Submission statuses
DO $$ BEGIN
    CREATE TYPE submission_status_enum AS ENUM (
        'not_started',
        'draft',
        'submitted',
        'not_participating'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ============================================================================
-- Main Consultation Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS public_consultations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- EC Identifiers
    initiative_id VARCHAR(50) NOT NULL UNIQUE,
    publication_id VARCHAR(50),

    -- Content
    title TEXT NOT NULL,
    short_title VARCHAR(200),
    description TEXT,
    full_description TEXT,
    objectives TEXT,
    target_group TEXT,

    -- Type and Status
    consultation_type consultation_type_enum NOT NULL DEFAULT 'initiative',
    status consultation_status_enum NOT NULL DEFAULT 'open',

    -- Responsible Entities
    dg_responsible VARCHAR(20),
    policy_areas VARCHAR[] DEFAULT '{}',

    -- Timeline
    start_date DATE,
    end_date DATE,

    -- Statistics
    feedback_count INTEGER DEFAULT 0,
    views_count INTEGER,
    feedback_by_country JSONB,
    feedback_by_category JSONB,

    -- URLs
    portal_url TEXT,
    feedback_url TEXT,

    -- Related Legislation
    com_references VARCHAR[] DEFAULT '{}',
    celex_numbers VARCHAR[] DEFAULT '{}',

    -- Outcome
    outcome_summary TEXT,
    outcome_published_date DATE,
    outcome_document_url TEXT,

    -- Relevance scoring
    relevance_score INTEGER DEFAULT 50,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    scraped_at TIMESTAMP,
    first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for public_consultations
CREATE INDEX IF NOT EXISTS ix_consultation_initiative_id ON public_consultations(initiative_id);
CREATE INDEX IF NOT EXISTS ix_consultation_status ON public_consultations(status);
CREATE INDEX IF NOT EXISTS ix_consultation_end_date ON public_consultations(end_date);
CREATE INDEX IF NOT EXISTS ix_consultation_dg ON public_consultations(dg_responsible);
CREATE INDEX IF NOT EXISTS ix_consultation_policy_areas ON public_consultations USING GIN(policy_areas);
CREATE INDEX IF NOT EXISTS ix_consultation_last_updated ON public_consultations(last_updated);

-- ============================================================================
-- Consultation Documents Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS consultation_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    consultation_id UUID NOT NULL REFERENCES public_consultations(id) ON DELETE CASCADE,

    -- Document info
    title VARCHAR(500) NOT NULL,
    document_type consultation_document_type_enum NOT NULL DEFAULT 'other',

    -- File info
    file_url TEXT,
    file_path TEXT,
    file_size INTEGER,
    file_format VARCHAR(20),
    language VARCHAR(5) DEFAULT 'en',

    -- Extracted content
    extracted_text TEXT,
    extraction_date TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for consultation_documents
CREATE INDEX IF NOT EXISTS ix_consultation_document_consultation ON consultation_documents(consultation_id);
CREATE INDEX IF NOT EXISTS ix_consultation_document_type ON consultation_documents(document_type);

-- ============================================================================
-- User Consultation Tracks Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_consultation_tracks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    consultation_id UUID NOT NULL REFERENCES public_consultations(id) ON DELETE CASCADE,

    -- Notification preferences
    notify_on_deadline BOOLEAN DEFAULT TRUE,
    notify_on_outcome BOOLEAN DEFAULT TRUE,
    notify_days_before INTEGER DEFAULT 7,

    -- Participation status
    submission_status submission_status_enum DEFAULT 'not_started',

    -- User notes
    notes TEXT,
    priority INTEGER DEFAULT 0,

    -- Timestamps
    tracked_since TIMESTAMP NOT NULL DEFAULT NOW(),
    last_notified_at TIMESTAMP,

    -- Unique constraint
    CONSTRAINT uq_user_consultation_track UNIQUE (user_id, consultation_id)
);

-- Indexes for user_consultation_tracks
CREATE INDEX IF NOT EXISTS ix_user_consultation_track_user ON user_consultation_tracks(user_id);
CREATE INDEX IF NOT EXISTS ix_user_consultation_track_consultation ON user_consultation_tracks(consultation_id);

-- ============================================================================
-- User Consultation Inputs Table (AI Proposals)
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_consultation_inputs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    consultation_id UUID NOT NULL REFERENCES public_consultations(id) ON DELETE CASCADE,

    -- AI Analysis
    ai_analysis TEXT,
    ai_analysis_date TIMESTAMP,
    ai_key_questions JSONB,

    -- AI Proposals (Blue tier)
    ai_proposals JSONB,
    ai_proposals_date TIMESTAMP,
    ai_model_used VARCHAR(50),
    ai_tokens_used INTEGER,

    -- User's Draft Response
    draft_response TEXT,
    draft_last_modified TIMESTAMP,

    -- Source Documents Used
    source_document_ids UUID[] DEFAULT '{}',

    -- Outcome Alignment
    alignment_score FLOAT,
    alignment_analysis TEXT,
    alignment_date TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Unique constraint
    CONSTRAINT uq_user_consultation_input UNIQUE (user_id, consultation_id)
);

-- Indexes for user_consultation_inputs
CREATE INDEX IF NOT EXISTS ix_user_consultation_input_user ON user_consultation_inputs(user_id);
CREATE INDEX IF NOT EXISTS ix_user_consultation_input_consultation ON user_consultation_inputs(consultation_id);

-- ============================================================================
-- Consultation Status History Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS consultation_status_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    consultation_id UUID NOT NULL REFERENCES public_consultations(id) ON DELETE CASCADE,

    old_status consultation_status_enum,
    new_status consultation_status_enum NOT NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT NOW(),

    notes TEXT,
    detected_during_sync BOOLEAN DEFAULT TRUE
);

-- Indexes for consultation_status_history
CREATE INDEX IF NOT EXISTS ix_consultation_status_history_consultation ON consultation_status_history(consultation_id);
CREATE INDEX IF NOT EXISTS ix_consultation_status_history_changed_at ON consultation_status_history(changed_at);

-- ============================================================================
-- Update Trigger for updated_at
-- ============================================================================

-- Create or replace function for updating timestamps
CREATE OR REPLACE FUNCTION update_consultation_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    NEW.last_updated = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to public_consultations
DROP TRIGGER IF EXISTS trigger_update_consultation_timestamp ON public_consultations;
CREATE TRIGGER trigger_update_consultation_timestamp
    BEFORE UPDATE ON public_consultations
    FOR EACH ROW
    EXECUTE FUNCTION update_consultation_updated_at();

-- Apply trigger to user_consultation_inputs
DROP TRIGGER IF EXISTS trigger_update_consultation_input_timestamp ON user_consultation_inputs;
CREATE TRIGGER trigger_update_consultation_input_timestamp
    BEFORE UPDATE ON user_consultation_inputs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE public_consultations IS 'EC Have Your Say public consultations';
COMMENT ON TABLE consultation_documents IS 'Documents attached to public consultations';
COMMENT ON TABLE user_consultation_tracks IS 'User subscriptions to consultations';
COMMENT ON TABLE user_consultation_inputs IS 'User inputs and AI proposals for consultations';
COMMENT ON TABLE consultation_status_history IS 'Status change history for consultations';

COMMENT ON COLUMN public_consultations.initiative_id IS 'EC initiative ID (unique identifier)';
COMMENT ON COLUMN public_consultations.dg_responsible IS 'Lead Directorate-General code';
COMMENT ON COLUMN public_consultations.relevance_score IS 'Calculated relevance score (0-100)';
COMMENT ON COLUMN user_consultation_inputs.ai_proposals IS 'AI-generated response proposals (Blue tier)';
COMMENT ON COLUMN user_consultation_inputs.alignment_score IS 'How well outcome aligned with user input (0-100)';
