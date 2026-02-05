-- Migration 014: Add EP Voting Tables
-- Phase 1.1: EP Voting Data Collection from HowTheyVote.eu
-- Created: February 2026

-- Create enum types
DO $$ BEGIN
    CREATE TYPE vote_position_enum AS ENUM ('FOR', 'AGAINST', 'ABSTENTION', 'DID_NOT_VOTE');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE vote_result_enum AS ENUM ('ADOPTED', 'REJECTED', 'UNKNOWN');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE procedure_type_enum AS ENUM ('COD', 'CNS', 'APP', 'NLE', 'INI', 'INL', 'RSP', 'BUD', 'DEC', 'OTHER');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- EP Political Groups
CREATE TABLE IF NOT EXISTS ep_political_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(20) NOT NULL UNIQUE,
    official_label VARCHAR(255) NOT NULL,
    label VARCHAR(100) NOT NULL,
    short_label VARCHAR(20),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ep_political_groups_code ON ep_political_groups(code);

COMMENT ON TABLE ep_political_groups IS 'EP Political Groups (EPP, S&D, Renew, etc.) from HowTheyVote';

-- EP Sections (within groups)
CREATE TABLE IF NOT EXISTS ep_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_code VARCHAR(20) NOT NULL REFERENCES ep_political_groups(code),
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_section_group_code UNIQUE (group_code, code)
);

COMMENT ON TABLE ep_sections IS 'Sections within EP groups (Greens vs EFA, ALDE vs EDP)';

-- EP Delegations
CREATE TABLE IF NOT EXISTS ep_delegations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_code VARCHAR(20) NOT NULL,
    section_id UUID REFERENCES ep_sections(id),
    country_code VARCHAR(3) NOT NULL,
    name VARCHAR(255) NOT NULL,
    parties_included TEXT[],
    num_meps INTEGER DEFAULT 0,
    delegation_chair VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ep_delegations_country ON ep_delegations(country_code);
CREATE INDEX IF NOT EXISTS ix_ep_delegations_group_country ON ep_delegations(group_code, country_code);

COMMENT ON TABLE ep_delegations IS 'National party delegations within EP groups';

-- EP Members
CREATE TABLE IF NOT EXISTS ep_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    htv_id INTEGER NOT NULL UNIQUE,
    ep_id INTEGER,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    country_code VARCHAR(3) NOT NULL,
    date_of_birth DATE,
    national_party VARCHAR(255),
    national_party_abbrev VARCHAR(50),
    current_group_code VARCHAR(20),
    delegation_id UUID REFERENCES ep_delegations(id),
    email VARCHAR(255),
    twitter VARCHAR(100),
    facebook VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    term INTEGER DEFAULT 10,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ep_members_htv_id ON ep_members(htv_id);
CREATE INDEX IF NOT EXISTS ix_ep_members_ep_id ON ep_members(ep_id);
CREATE INDEX IF NOT EXISTS ix_ep_members_country ON ep_members(country_code);
CREATE INDEX IF NOT EXISTS ix_ep_members_full_name ON ep_members(full_name);
CREATE INDEX IF NOT EXISTS ix_ep_members_name ON ep_members(last_name, first_name);

COMMENT ON TABLE ep_members IS 'MEPs from HowTheyVote with national party enrichment';

-- EP Group Memberships
CREATE TABLE IF NOT EXISTS ep_group_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id UUID NOT NULL REFERENCES ep_members(id),
    group_code VARCHAR(20) NOT NULL REFERENCES ep_political_groups(code),
    term INTEGER NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ep_group_memberships_member ON ep_group_memberships(member_id);
CREATE INDEX IF NOT EXISTS ix_ep_group_memberships_group_term ON ep_group_memberships(group_code, term);

COMMENT ON TABLE ep_group_memberships IS 'MEP membership history in political groups';

-- EP Votes
CREATE TABLE IF NOT EXISTS ep_votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    htv_id INTEGER NOT NULL UNIQUE,
    timestamp TIMESTAMP NOT NULL,
    display_title TEXT NOT NULL,
    reference VARCHAR(100),
    description TEXT,
    amendment_subject VARCHAR(255),
    amendment_number VARCHAR(50),
    is_main BOOLEAN DEFAULT FALSE,
    procedure_reference VARCHAR(50),
    procedure_title TEXT,
    procedure_type procedure_type_enum,
    procedure_stage VARCHAR(100),
    count_for INTEGER DEFAULT 0,
    count_against INTEGER DEFAULT 0,
    count_abstention INTEGER DEFAULT 0,
    count_did_not_vote INTEGER DEFAULT 0,
    result vote_result_enum DEFAULT 'UNKNOWN',
    texts_adopted_reference VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ep_votes_htv_id ON ep_votes(htv_id);
CREATE INDEX IF NOT EXISTS ix_ep_votes_timestamp ON ep_votes(timestamp);
CREATE INDEX IF NOT EXISTS ix_ep_votes_reference ON ep_votes(reference);
CREATE INDEX IF NOT EXISTS ix_ep_votes_procedure ON ep_votes(procedure_reference);
CREATE INDEX IF NOT EXISTS ix_ep_votes_date ON ep_votes(timestamp);

COMMENT ON TABLE ep_votes IS 'Roll-call votes in EP from HowTheyVote';

-- EP Member Votes
CREATE TABLE IF NOT EXISTS ep_member_votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vote_id UUID NOT NULL REFERENCES ep_votes(id) ON DELETE CASCADE,
    member_id UUID NOT NULL REFERENCES ep_members(id),
    position vote_position_enum NOT NULL,
    country_code VARCHAR(3) NOT NULL,
    group_code VARCHAR(20) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_member_vote UNIQUE (vote_id, member_id)
);

CREATE INDEX IF NOT EXISTS ix_ep_member_votes_vote ON ep_member_votes(vote_id);
CREATE INDEX IF NOT EXISTS ix_ep_member_votes_member ON ep_member_votes(member_id);
CREATE INDEX IF NOT EXISTS ix_ep_member_votes_position ON ep_member_votes(position);
CREATE INDEX IF NOT EXISTS ix_ep_member_votes_group ON ep_member_votes(group_code);

COMMENT ON TABLE ep_member_votes IS 'Individual MEP voting positions per vote';

-- EP Committee Votes
CREATE TABLE IF NOT EXISTS ep_committee_votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vote_id UUID NOT NULL REFERENCES ep_votes(id) ON DELETE CASCADE,
    committee_code VARCHAR(10) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_committee_vote UNIQUE (vote_id, committee_code)
);

CREATE INDEX IF NOT EXISTS ix_ep_committee_votes_committee ON ep_committee_votes(committee_code);

COMMENT ON TABLE ep_committee_votes IS 'Responsible committees for each vote';

-- User Vote Tracking
CREATE TABLE IF NOT EXISTS user_vote_tracks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vote_id UUID REFERENCES ep_votes(id) ON DELETE CASCADE,
    procedure_reference VARCHAR(50),
    notes TEXT,
    notify_on_update BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_user_vote_tracks_user ON user_vote_tracks(user_id);
CREATE INDEX IF NOT EXISTS ix_user_vote_tracks_procedure ON user_vote_tracks(procedure_reference);

COMMENT ON TABLE user_vote_tracks IS 'User subscriptions to track votes/procedures';

-- EP Data Import Tracking
CREATE TABLE IF NOT EXISTS ep_data_imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(50) NOT NULL,
    import_type VARCHAR(50) NOT NULL,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    records_processed INTEGER DEFAULT 0,
    records_added INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_skipped INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    error_details JSONB,
    source_metadata JSONB,
    status VARCHAR(20) DEFAULT 'running'
);

COMMENT ON TABLE ep_data_imports IS 'Audit log for HowTheyVote data imports';

-- Seed initial political groups (from HowTheyVote)
INSERT INTO ep_political_groups (code, official_label, label, short_label) VALUES
    ('EPP', 'Group of the European People''s Party (Christian Democrats)', 'European People''s Party', 'EPP'),
    ('SD', 'Group of the Progressive Alliance of Socialists and Democrats in the European Parliament', 'Socialists & Democrats', 'S&D'),
    ('RENEW', 'Renew Europe Group', 'Renew Europe', 'Renew'),
    ('GREEN_EFA', 'Group of the Greens/European Free Alliance', 'Greens/EFA', 'Greens'),
    ('ECR', 'European Conservatives and Reformists Group', 'European Conservatives', 'ECR'),
    ('GUE_NGL', 'The Left group in the European Parliament - GUE/NGL', 'The Left', 'Left'),
    ('PFE', 'Patriots for Europe Group', 'Patriots for Europe', 'PfE'),
    ('ESN', 'Europe of Sovereign Nations Group', 'Europe of Sovereign Nations', 'ESN'),
    ('NI', 'Non-attached Members', 'Non-Inscrits', 'NI')
ON CONFLICT (code) DO UPDATE SET
    official_label = EXCLUDED.official_label,
    label = EXCLUDED.label,
    short_label = EXCLUDED.short_label,
    updated_at = NOW();

-- Seed sections for Greens/EFA and Renew
INSERT INTO ep_sections (group_code, code, name, description) VALUES
    ('GREEN_EFA', 'GREENS', 'The Greens', 'Green parties within Greens/EFA'),
    ('GREEN_EFA', 'EFA', 'European Free Alliance', 'Regionalist and nationalist parties within Greens/EFA'),
    ('RENEW', 'ALDE', 'ALDE Party', 'Alliance of Liberals and Democrats for Europe'),
    ('RENEW', 'EDP', 'European Democratic Party', 'European Democratic Party - centrist component')
ON CONFLICT ON CONSTRAINT uq_section_group_code DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    updated_at = NOW();
