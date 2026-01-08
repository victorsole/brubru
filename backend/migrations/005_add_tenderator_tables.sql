-- Tenderator Tables Migration
-- EU Public Procurement Tender Monitoring System
-- Part of Tenderator feature for Blue-tier users
--
-- Run this migration against your Supabase database:
--   psql $DATABASE_URL -f backend/migrations/005_add_tenderator_tables.sql

-- ============================================================================
-- 1. Tenders Table - Stores EU procurement notices from TED
-- ============================================================================

CREATE TABLE IF NOT EXISTS tenders (
    id SERIAL PRIMARY KEY,

    -- TED identifiers
    publication_number VARCHAR(50) UNIQUE NOT NULL,
    notice_id VARCHAR(100),
    form_type VARCHAR(50),
    notice_subtype VARCHAR(20),

    -- Basic info
    title TEXT NOT NULL,
    description TEXT,
    official_name VARCHAR(500),
    buyer_country VARCHAR(2),

    -- Procedure
    procedure_type VARCHAR(50),
    legal_basis VARCHAR(50),

    -- Classification
    cpv_codes TEXT[],
    cpv_main VARCHAR(20),
    nuts_codes TEXT[],
    contract_nature VARCHAR(20),

    -- Value
    estimated_value FLOAT,
    estimated_value_currency VARCHAR(3) DEFAULT 'EUR',
    value_range_low FLOAT,
    value_range_high FLOAT,

    -- Dates
    publication_date TIMESTAMPTZ,
    submission_deadline TIMESTAMPTZ,
    contract_start_date TIMESTAMPTZ,
    contract_duration_months INTEGER,

    -- Award criteria
    award_criteria_type VARCHAR(50),
    award_criteria JSONB,

    -- Requirements
    selection_criteria JSONB,
    exclusion_grounds JSONB,
    minimum_requirements JSONB,

    -- Lots
    has_lots BOOLEAN DEFAULT FALSE,
    lot_count INTEGER,
    lots JSONB,

    -- Documents and links
    ted_url VARCHAR(500),
    documents_url VARCHAR(500),
    submission_url VARCHAR(500),

    -- Raw data
    xml_content TEXT,
    raw_json JSONB,

    -- AI enrichment
    sme_suitability_score FLOAT,
    sme_analysis JSONB,
    summary TEXT,
    keywords TEXT[],
    embeddings_id VARCHAR(100),

    -- Status
    status VARCHAR(20) DEFAULT 'open',
    is_framework BOOLEAN DEFAULT FALSE,
    is_joint_procurement BOOLEAN DEFAULT FALSE,

    -- Metadata
    source VARCHAR(50) DEFAULT 'ted_api',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_synced_at TIMESTAMPTZ
);

-- Indexes for tenders
CREATE INDEX IF NOT EXISTS idx_tenders_publication_number ON tenders(publication_number);
CREATE INDEX IF NOT EXISTS idx_tenders_publication_date ON tenders(publication_date DESC);
CREATE INDEX IF NOT EXISTS idx_tenders_submission_deadline ON tenders(submission_deadline);
CREATE INDEX IF NOT EXISTS idx_tenders_status ON tenders(status);
CREATE INDEX IF NOT EXISTS idx_tenders_buyer_country ON tenders(buyer_country);
CREATE INDEX IF NOT EXISTS idx_tenders_cpv_main ON tenders(cpv_main);
CREATE INDEX IF NOT EXISTS idx_tenders_procedure_type ON tenders(procedure_type);
CREATE INDEX IF NOT EXISTS idx_tenders_form_type ON tenders(form_type);
CREATE INDEX IF NOT EXISTS idx_tenders_sme_score ON tenders(sme_suitability_score DESC);
CREATE INDEX IF NOT EXISTS idx_tenders_status_deadline ON tenders(status, submission_deadline);

-- GIN index for CPV array queries
CREATE INDEX IF NOT EXISTS idx_tenders_cpv_codes_gin ON tenders USING GIN(cpv_codes);

-- ============================================================================
-- 2. Tender Profiles Table - User preferences for matching
-- ============================================================================

CREATE TABLE IF NOT EXISTS tender_profiles (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Company information
    company_name VARCHAR(300),
    company_size VARCHAR(20), -- micro, small, medium
    annual_turnover FLOAT,
    employee_count INTEGER,
    years_in_business INTEGER,

    -- Sector preferences
    cpv_categories TEXT[],
    cpv_codes TEXT[],
    sectors_description TEXT,

    -- Geographic preferences
    countries_of_interest TEXT[],
    nuts_regions TEXT[],
    eu_wide BOOLEAN DEFAULT TRUE,

    -- Value preferences
    min_tender_value FLOAT,
    max_tender_value FLOAT,
    preferred_currency VARCHAR(3) DEFAULT 'EUR',

    -- Procedure preferences
    preferred_procedures TEXT[],
    exclude_frameworks BOOLEAN DEFAULT FALSE,
    exclude_joint_procurement BOOLEAN DEFAULT FALSE,

    -- Matching preferences
    keywords TEXT[],
    excluded_keywords TEXT[],
    min_deadline_days INTEGER DEFAULT 30,

    -- Capabilities
    certifications TEXT[],
    past_contract_value FLOAT,
    references_count INTEGER,

    -- Notification preferences
    notification_frequency VARCHAR(20) DEFAULT 'weekly',
    notification_email BOOLEAN DEFAULT TRUE,
    notification_in_app BOOLEAN DEFAULT TRUE,
    max_matches_per_digest INTEGER DEFAULT 10,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_matched_at TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- One profile per user
    UNIQUE(user_id)
);

-- Indexes for tender_profiles
CREATE INDEX IF NOT EXISTS idx_tender_profiles_user ON tender_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_tender_profiles_active ON tender_profiles(is_active);

-- ============================================================================
-- 3. Tender Matches Table - Links tenders to users with scores
-- ============================================================================

CREATE TABLE IF NOT EXISTS tender_matches (
    id SERIAL PRIMARY KEY,

    -- Foreign keys
    tender_id INTEGER NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    profile_id INTEGER NOT NULL REFERENCES tender_profiles(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Match scoring
    match_score FLOAT NOT NULL,
    match_reasons JSONB,
    match_details TEXT,

    -- User actions
    is_viewed BOOLEAN DEFAULT FALSE,
    is_saved BOOLEAN DEFAULT FALSE,
    is_dismissed BOOLEAN DEFAULT FALSE,
    is_applied BOOLEAN DEFAULT FALSE,

    -- User notes
    user_notes TEXT,
    user_rating INTEGER CHECK (user_rating >= 1 AND user_rating <= 5),

    -- Notification tracking
    notified_at TIMESTAMPTZ,
    notification_method VARCHAR(20),

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Prevent duplicate matches
    UNIQUE(tender_id, profile_id)
);

-- Indexes for tender_matches
CREATE INDEX IF NOT EXISTS idx_tender_matches_user ON tender_matches(user_id);
CREATE INDEX IF NOT EXISTS idx_tender_matches_tender ON tender_matches(tender_id);
CREATE INDEX IF NOT EXISTS idx_tender_matches_profile ON tender_matches(profile_id);
CREATE INDEX IF NOT EXISTS idx_tender_matches_score ON tender_matches(match_score DESC);
CREATE INDEX IF NOT EXISTS idx_tender_matches_saved ON tender_matches(is_saved) WHERE is_saved = TRUE;
CREATE INDEX IF NOT EXISTS idx_tender_matches_not_dismissed ON tender_matches(user_id, match_score DESC) WHERE is_dismissed = FALSE;

-- ============================================================================
-- 4. Tender Fetch Jobs Table - Track fetch operations
-- ============================================================================

CREATE TABLE IF NOT EXISTS tender_fetch_jobs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(50) UNIQUE NOT NULL,

    -- Job configuration
    job_type VARCHAR(50),
    source VARCHAR(50),
    query_params JSONB,

    -- Results
    status VARCHAR(20) DEFAULT 'pending',
    tenders_found INTEGER DEFAULT 0,
    tenders_new INTEGER DEFAULT 0,
    tenders_updated INTEGER DEFAULT 0,
    errors JSONB,

    -- Timing
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_seconds FLOAT,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for tender_fetch_jobs
CREATE INDEX IF NOT EXISTS idx_tender_fetch_jobs_status ON tender_fetch_jobs(status);
CREATE INDEX IF NOT EXISTS idx_tender_fetch_jobs_created ON tender_fetch_jobs(created_at DESC);

-- ============================================================================
-- 5. Updated_at Trigger Function
-- ============================================================================

-- Create trigger function if it doesn't exist
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers to tender tables
DROP TRIGGER IF EXISTS update_tenders_updated_at ON tenders;
CREATE TRIGGER update_tenders_updated_at
    BEFORE UPDATE ON tenders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_tender_profiles_updated_at ON tender_profiles;
CREATE TRIGGER update_tender_profiles_updated_at
    BEFORE UPDATE ON tender_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_tender_matches_updated_at ON tender_matches;
CREATE TRIGGER update_tender_matches_updated_at
    BEFORE UPDATE ON tender_matches
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 6. Row Level Security (RLS) Policies
-- ============================================================================

-- Enable RLS on tender tables
ALTER TABLE tender_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE tender_matches ENABLE ROW LEVEL SECURITY;

-- Tender profiles: Users can only see/modify their own profile
CREATE POLICY tender_profiles_user_policy ON tender_profiles
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- Tender matches: Users can only see/modify their own matches
CREATE POLICY tender_matches_user_policy ON tender_matches
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- Tenders are publicly readable (no auth required)
-- But only admins/system can insert/update
ALTER TABLE tenders ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenders_read_policy ON tenders
    FOR SELECT
    USING (TRUE);

-- Note: Insert/Update policies for tenders should be handled by service role
-- CREATE POLICY tenders_admin_policy ON tenders
--     FOR ALL
--     USING (auth.role() = 'service_role')
--     WITH CHECK (auth.role() = 'service_role');

-- ============================================================================
-- 7. Comments for Documentation
-- ============================================================================

COMMENT ON TABLE tenders IS 'EU public procurement tenders from TED (Tenders Electronic Daily)';
COMMENT ON TABLE tender_profiles IS 'User preferences for tender matching (Blue-tier only)';
COMMENT ON TABLE tender_matches IS 'Matched tenders for users with scores and actions';
COMMENT ON TABLE tender_fetch_jobs IS 'Tracking of tender fetch operations';

COMMENT ON COLUMN tenders.publication_number IS 'TED publication number (e.g., 1776-2025)';
COMMENT ON COLUMN tenders.cpv_codes IS 'Common Procurement Vocabulary codes';
COMMENT ON COLUMN tenders.nuts_codes IS 'NUTS geographic region codes';
COMMENT ON COLUMN tenders.sme_suitability_score IS 'AI-calculated SME accessibility score (0-100)';

COMMENT ON COLUMN tender_profiles.company_size IS 'SME category: micro, small, medium';
COMMENT ON COLUMN tender_profiles.cpv_categories IS 'CPV code prefixes of interest (e.g., 72 for IT)';
COMMENT ON COLUMN tender_profiles.min_deadline_days IS 'Minimum days until deadline to consider';

COMMENT ON COLUMN tender_matches.match_score IS 'Overall match score (0-100)';
COMMENT ON COLUMN tender_matches.match_reasons IS 'JSON breakdown of score by criteria';

-- ============================================================================
-- 8. Tenderator Settings Table (Singleton for system configuration)
-- ============================================================================

CREATE TABLE IF NOT EXISTS tenderator_settings (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- Singleton pattern

    -- Fetch settings
    default_max_value FLOAT DEFAULT 5000000.0,
    fetch_frequency VARCHAR(20) DEFAULT 'weekly',  -- daily, weekly, bi-weekly
    enabled_countries TEXT[],  -- NULL means all countries
    enabled_cpv_codes TEXT[],  -- NULL means all CPV codes

    -- Matching settings
    auto_matching_enabled BOOLEAN DEFAULT TRUE,
    match_score_threshold FLOAT DEFAULT 50.0,

    -- Notification settings
    auto_notifications_enabled BOOLEAN DEFAULT TRUE,

    -- Metadata
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by INTEGER REFERENCES users(id)
);

-- Insert default settings if table is empty
INSERT INTO tenderator_settings (id)
SELECT 1
WHERE NOT EXISTS (SELECT 1 FROM tenderator_settings WHERE id = 1);

-- Auto-update updated_at on changes
CREATE OR REPLACE FUNCTION update_tenderator_settings_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tenderator_settings_updated_at ON tenderator_settings;
CREATE TRIGGER tenderator_settings_updated_at
    BEFORE UPDATE ON tenderator_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_tenderator_settings_timestamp();

COMMENT ON TABLE tenderator_settings IS 'System configuration for Tenderator feature (singleton table)';

-- ============================================================================
-- Migration Complete
-- ============================================================================

-- Verify tables were created
DO $$
BEGIN
    RAISE NOTICE 'Tenderator migration complete!';
    RAISE NOTICE 'Created tables: tenders, tender_profiles, tender_matches, tender_fetch_jobs, tenderator_settings';
END $$;
