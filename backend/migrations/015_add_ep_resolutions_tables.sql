-- Migration 015: Add EP Resolutions Tables
-- Phase 1.3: Resolution-to-Legislation Mapping
-- Created: February 2026

-- Create enum types
DO $$ BEGIN
    CREATE TYPE resolution_type_enum AS ENUM ('INL', 'INI', 'RSP', 'OTHER');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE match_method_enum AS ENUM (
        'OEIL_CROSSREF',
        'COMMISSION_FOLLOWUP',
        'TITLE_SIMILARITY',
        'EUROVOC_MATCH',
        'MANUAL'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- EP Resolutions
CREATE TABLE IF NOT EXISTS ep_resolutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Procedure identification
    procedure_ref VARCHAR(50) NOT NULL UNIQUE,
    title TEXT NOT NULL,
    resolution_type resolution_type_enum NOT NULL,

    -- Dates
    adoption_date DATE,
    vote_date TIMESTAMP,

    -- Committee info
    lead_committee VARCHAR(10),
    rapporteur VARCHAR(255),

    -- Content
    summary TEXT,
    eurovoc_codes TEXT[],
    policy_areas TEXT[],

    -- Vote results
    vote_for INTEGER DEFAULT 0,
    vote_against INTEGER DEFAULT 0,
    vote_abstention INTEGER DEFAULT 0,
    vote_total INTEGER DEFAULT 0,

    -- Links
    oeil_url VARCHAR(500),
    text_url VARCHAR(500),

    -- Status
    has_commission_followup BOOLEAN DEFAULT FALSE,
    followup_checked_at TIMESTAMP,

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ep_resolutions_procedure_ref ON ep_resolutions(procedure_ref);
CREATE INDEX IF NOT EXISTS ix_ep_resolutions_type ON ep_resolutions(resolution_type);
CREATE INDEX IF NOT EXISTS ix_ep_resolutions_adoption_date ON ep_resolutions(adoption_date);
CREATE INDEX IF NOT EXISTS ix_ep_resolutions_lead_committee ON ep_resolutions(lead_committee);
CREATE INDEX IF NOT EXISTS ix_ep_resolutions_type_date ON ep_resolutions(resolution_type, adoption_date);

COMMENT ON TABLE ep_resolutions IS 'EP resolutions (INL, INI, RSP) that may precede legislation';

-- Resolution MEP Votes
CREATE TABLE IF NOT EXISTS resolution_mep_votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resolution_id UUID NOT NULL REFERENCES ep_resolutions(id) ON DELETE CASCADE,
    mep_id UUID NOT NULL REFERENCES ep_members(id),

    vote VARCHAR(20) NOT NULL,
    group_code VARCHAR(20),
    country_code VARCHAR(3),

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_resolution_mep_vote UNIQUE (resolution_id, mep_id)
);

CREATE INDEX IF NOT EXISTS ix_resolution_mep_votes_mep ON resolution_mep_votes(mep_id);
CREATE INDEX IF NOT EXISTS ix_resolution_mep_votes_resolution ON resolution_mep_votes(resolution_id);

COMMENT ON TABLE resolution_mep_votes IS 'Individual MEP votes on resolutions for prediction';

-- Resolution to Legislation Links
CREATE TABLE IF NOT EXISTS resolution_to_legislation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source resolution
    resolution_id UUID NOT NULL REFERENCES ep_resolutions(id) ON DELETE CASCADE,

    -- Target legislation
    legislative_procedure_ref VARCHAR(50) NOT NULL,
    legislative_title TEXT,
    carriage_id UUID REFERENCES legislative_carriages(id) ON DELETE SET NULL,

    -- Match info
    match_method match_method_enum NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    match_details JSONB,

    -- Timing
    days_to_proposal INTEGER,

    -- Verification
    verified BOOLEAN DEFAULT FALSE,
    verified_by VARCHAR(255),
    verified_at TIMESTAMP,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_resolution_legislation UNIQUE (resolution_id, legislative_procedure_ref)
);

CREATE INDEX IF NOT EXISTS ix_resolution_legislation_procedure ON resolution_to_legislation(legislative_procedure_ref);
CREATE INDEX IF NOT EXISTS ix_resolution_legislation_method ON resolution_to_legislation(match_method);
CREATE INDEX IF NOT EXISTS ix_resolution_legislation_confidence ON resolution_to_legislation(confidence);

COMMENT ON TABLE resolution_to_legislation IS 'Links resolutions to related legislative procedures';

-- Commission Followups
CREATE TABLE IF NOT EXISTS commission_followups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    resolution_id UUID NOT NULL REFERENCES ep_resolutions(id) ON DELETE CASCADE,

    -- Commission response
    com_reference VARCHAR(100),
    followup_date DATE,
    followup_type VARCHAR(50),

    -- Content
    title TEXT,
    summary TEXT,
    document_url VARCHAR(500),

    -- Status
    results_in_legislation BOOLEAN DEFAULT FALSE,
    legislative_ref VARCHAR(50),

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_commission_followups_resolution ON commission_followups(resolution_id);

COMMENT ON TABLE commission_followups IS 'Commission follow-up to EP resolutions';
