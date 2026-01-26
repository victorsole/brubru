-- Migration: Create Legislative Train tracking tables
-- Created: 2025-01-19
-- Purpose: Full Legislative Train Schedule tracking with packages, carriages, and user subscriptions
--
-- Tables:
--   1. legislative_trains - EC Priority 'trains' (7 priorities for 2024-2029 Commission)
--   2. legislative_packages - Package hierarchy within trains (NEW in January 2025)
--   3. legislative_carriages - Individual legislative files
--   4. carriage_status_history - Historical status changes
--   5. user_carriage_tracks - User subscriptions to files

-- ============================================================================
-- 1. ENUMS
-- ============================================================================

DO $$ BEGIN
    CREATE TYPE carriage_status_enum AS ENUM (
        'announced',
        'legislative_initiative',
        'tabled',
        'close_to_adoption',
        'completed',
        'adopted',
        'blocked',
        'withdrawn'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE text_type_enum AS ENUM (
        'legislative',
        'non_legislative',
        'unknown'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ============================================================================
-- 2. LEGISLATIVE TRAINS (EC Priorities)
-- ============================================================================

CREATE TABLE IF NOT EXISTS legislative_trains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    priority_number INT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    commission_term TEXT DEFAULT '2024-2029',
    theme_slug TEXT,

    -- Statistics (computed from carriages)
    total_files INT DEFAULT 0,
    files_by_status JSON DEFAULT '{}',

    -- URLs
    url TEXT,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_legislative_trains_priority ON legislative_trains(priority_number);
CREATE INDEX IF NOT EXISTS idx_legislative_trains_theme_slug ON legislative_trains(theme_slug);

COMMENT ON TABLE legislative_trains IS 'EC Priority trains (7 priorities for 2024-2029 Commission)';
COMMENT ON COLUMN legislative_trains.priority_number IS 'Priority number 1-7';
COMMENT ON COLUMN legislative_trains.files_by_status IS 'JSON object with status counts: {"announced": 15, "tabled": 72, ...}';

-- ============================================================================
-- 3. LEGISLATIVE PACKAGES (NEW January 2025)
-- ============================================================================

CREATE TABLE IF NOT EXISTS legislative_packages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    train_id UUID REFERENCES legislative_trains(id) ON DELETE SET NULL,

    -- Identifiers
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,

    -- Hierarchy (packages can have sub-packages)
    parent_id UUID REFERENCES legislative_packages(id) ON DELETE SET NULL,
    parent_slug TEXT,
    is_sub_package BOOLEAN DEFAULT FALSE,

    -- Status counts
    status_announced INT DEFAULT 0,
    status_tabled INT DEFAULT 0,
    status_blocked INT DEFAULT 0,
    status_close_to_adoption INT DEFAULT 0,
    status_adopted INT DEFAULT 0,
    status_withdrawn INT DEFAULT 0,
    total_files INT DEFAULT 0,

    -- Filter metadata
    ec_priorities TEXT[] DEFAULT '{}',
    ep_committees TEXT[] DEFAULT '{}',

    -- URLs
    url TEXT,

    -- Timestamps
    scraped_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_legislative_packages_train_id ON legislative_packages(train_id);
CREATE INDEX IF NOT EXISTS idx_legislative_packages_slug ON legislative_packages(slug);
CREATE INDEX IF NOT EXISTS idx_legislative_packages_parent_id ON legislative_packages(parent_id);
CREATE INDEX IF NOT EXISTS idx_legislative_packages_is_sub_package ON legislative_packages(is_sub_package);

COMMENT ON TABLE legislative_packages IS 'Thematic packages within Legislative Train (supports hierarchy via parent_id)';
COMMENT ON COLUMN legislative_packages.slug IS 'URL slug, e.g., "package-vision-for-agriculture"';
COMMENT ON COLUMN legislative_packages.parent_id IS 'Parent package ID for sub-packages';

-- ============================================================================
-- 4. LEGISLATIVE CARRIAGES (Individual Files)
-- ============================================================================

CREATE TABLE IF NOT EXISTS legislative_carriages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    train_id UUID REFERENCES legislative_trains(id) ON DELETE SET NULL,
    package_id UUID REFERENCES legislative_packages(id) ON DELETE SET NULL,

    -- External IDs
    file_id TEXT UNIQUE NOT NULL,
    package_slug TEXT,

    -- Basic info
    title TEXT NOT NULL,
    description TEXT,

    -- Status tracking
    current_status carriage_status_enum NOT NULL,
    status_history JSON DEFAULT '[]',
    days_in_current_status INT,
    is_blocked BOOLEAN DEFAULT FALSE,

    -- Timeline (monthly status snapshots)
    timeline JSON DEFAULT '[]',

    -- Text type and spotlight
    text_type text_type_enum DEFAULT 'unknown',
    spotlight_tags TEXT[] DEFAULT '{}',
    is_recently_updated BOOLEAN DEFAULT FALSE,

    -- Cross-references
    oeil_procedure_ref TEXT,
    celex_numbers TEXT[] DEFAULT '{}',
    eprs_briefing_ids TEXT[] DEFAULT '{}',

    -- Stakeholders
    lead_committee TEXT,
    opinion_committees TEXT[] DEFAULT '{}',
    committees TEXT[] DEFAULT '{}',
    rapporteur_mep_id TEXT,

    -- Filter metadata
    ec_priority_ids TEXT[] DEFAULT '{}',
    related_themes TEXT[] DEFAULT '{}',

    -- OEIL enrichment data
    oeil_procedure_data JSON,
    oeil_timeline JSON DEFAULT '[]',
    oeil_key_events JSON DEFAULT '[]',

    -- EUR-Lex enrichment data
    eurlex_documents JSON DEFAULT '[]',
    legal_text_url TEXT,

    -- EPRS enrichment data
    eprs_matched_briefings JSON DEFAULT '[]',
    eprs_match_confidence INT,

    -- Policy areas
    policy_areas TEXT[] DEFAULT '{}',

    -- AI-generated enrichment (Hugging Face)
    ai_summary TEXT,
    ai_entities JSON DEFAULT '[]',
    ai_policy_classifications JSON DEFAULT '[]',

    -- URLs
    url TEXT,

    -- Timestamps
    scraped_at TIMESTAMP DEFAULT NOW(),
    first_seen TIMESTAMP DEFAULT NOW(),
    last_updated TIMESTAMP DEFAULT NOW(),
    expected_completion TIMESTAMP,
    enriched_at TIMESTAMP,
    enrichment_quality TEXT
);

CREATE INDEX IF NOT EXISTS idx_legislative_carriages_train_id ON legislative_carriages(train_id);
CREATE INDEX IF NOT EXISTS idx_legislative_carriages_package_id ON legislative_carriages(package_id);
CREATE INDEX IF NOT EXISTS idx_legislative_carriages_file_id ON legislative_carriages(file_id);
CREATE INDEX IF NOT EXISTS idx_legislative_carriages_current_status ON legislative_carriages(current_status);
CREATE INDEX IF NOT EXISTS idx_legislative_carriages_oeil_procedure_ref ON legislative_carriages(oeil_procedure_ref);
CREATE INDEX IF NOT EXISTS idx_legislative_carriages_lead_committee ON legislative_carriages(lead_committee);
CREATE INDEX IF NOT EXISTS idx_legislative_carriages_is_blocked ON legislative_carriages(is_blocked);
CREATE INDEX IF NOT EXISTS idx_legislative_carriages_last_updated ON legislative_carriages(last_updated);
CREATE INDEX IF NOT EXISTS idx_legislative_carriages_text_type ON legislative_carriages(text_type);

-- Full-text search index on title
CREATE INDEX IF NOT EXISTS idx_legislative_carriages_title_gin ON legislative_carriages USING gin(to_tsvector('english', title));

-- Index for CELEX array contains queries
CREATE INDEX IF NOT EXISTS idx_legislative_carriages_celex_gin ON legislative_carriages USING gin(celex_numbers);

COMMENT ON TABLE legislative_carriages IS 'Individual legislative files within the Legislative Train';
COMMENT ON COLUMN legislative_carriages.file_id IS 'Legislative Train internal ID/slug';
COMMENT ON COLUMN legislative_carriages.oeil_procedure_ref IS 'OEIL procedure reference, e.g., "2021/0106(COD)"';
COMMENT ON COLUMN legislative_carriages.celex_numbers IS 'Array of EUR-Lex CELEX numbers';
COMMENT ON COLUMN legislative_carriages.timeline IS 'Monthly status snapshots: [{year, month, status, is_current}, ...]';
COMMENT ON COLUMN legislative_carriages.spotlight_tags IS 'Tags like "Deal reached", "Vote held", etc.';
COMMENT ON COLUMN legislative_carriages.enrichment_quality IS 'Quality level: "high", "medium", "low"';

-- ============================================================================
-- 5. CARRIAGE STATUS HISTORY
-- ============================================================================

CREATE TABLE IF NOT EXISTS carriage_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    carriage_id UUID NOT NULL REFERENCES legislative_carriages(id) ON DELETE CASCADE,

    status carriage_status_enum NOT NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    duration_days INT,

    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_carriage_status_history_carriage_id ON carriage_status_history(carriage_id);
CREATE INDEX IF NOT EXISTS idx_carriage_status_history_changed_at ON carriage_status_history(changed_at);
CREATE INDEX IF NOT EXISTS idx_carriage_status_history_status ON carriage_status_history(status);

COMMENT ON TABLE carriage_status_history IS 'Historical status changes for trend analysis';
COMMENT ON COLUMN carriage_status_history.duration_days IS 'Days spent in previous status';

-- ============================================================================
-- 6. USER CARRIAGE TRACKS (Subscriptions)
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_carriage_tracks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    carriage_id UUID NOT NULL REFERENCES legislative_carriages(id) ON DELETE CASCADE,

    -- Notification preferences
    notify_on_status_change BOOLEAN DEFAULT TRUE,
    notify_on_blocking BOOLEAN DEFAULT TRUE,
    notify_on_new_documents BOOLEAN DEFAULT TRUE,

    -- Tracking metadata
    tracked_since TIMESTAMP NOT NULL DEFAULT NOW(),
    last_notified_at TIMESTAMP,

    -- Unique constraint: one track per user per carriage
    UNIQUE(user_id, carriage_id)
);

CREATE INDEX IF NOT EXISTS idx_user_carriage_tracks_user_id ON user_carriage_tracks(user_id);
CREATE INDEX IF NOT EXISTS idx_user_carriage_tracks_carriage_id ON user_carriage_tracks(carriage_id);

COMMENT ON TABLE user_carriage_tracks IS 'User subscriptions to legislative files for status updates';
COMMENT ON COLUMN user_carriage_tracks.notify_on_blocking IS 'Notify when file blocked 9+ months';

-- ============================================================================
-- 7. TRIGGER: Auto-update updated_at timestamps
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_legislative_trains_updated_at ON legislative_trains;
CREATE TRIGGER update_legislative_trains_updated_at
    BEFORE UPDATE ON legislative_trains
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_legislative_packages_updated_at ON legislative_packages;
CREATE TRIGGER update_legislative_packages_updated_at
    BEFORE UPDATE ON legislative_packages
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_legislative_carriages_updated_at ON legislative_carriages;
CREATE TRIGGER update_legislative_carriages_updated_at
    BEFORE UPDATE ON legislative_carriages
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- DONE
-- ============================================================================
