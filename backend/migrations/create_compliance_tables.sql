-- ============================================================================
-- EU Law Comply: Compliance Engine Database Schema
-- ============================================================================
-- Description: Tables for requirement extraction, gap analysis, and
--              compliance tracking
-- Created: 2025-11-17
-- Version: 1.0
-- ============================================================================

-- ============================================================================
-- 1. LAW REQUIREMENTS TABLE
-- ============================================================================
-- Stores extracted obligations/requirements from EU laws
-- Pre-extracted using NLP + LLM to identify "shall", "must", "required to"

CREATE TABLE IF NOT EXISTS law_requirements (
    id SERIAL PRIMARY KEY,
    law_id INTEGER NOT NULL REFERENCES eu_laws(id) ON DELETE CASCADE,
    cluster_id INTEGER REFERENCES law_clusters(id) ON DELETE SET NULL,

    -- Requirement identification
    article_number VARCHAR(50),              -- e.g., "Article 15", "Art. 24(1)"
    requirement_text TEXT NOT NULL,          -- Full obligation text
    requirement_summary VARCHAR(500),        -- Short summary for display

    -- Classification
    obligation_type VARCHAR(50),             -- 'must', 'shall', 'should', 'may'
    applicable_to VARCHAR(200),              -- Who must comply (e.g., "VLOPs", "all platforms")

    -- Timing
    deadline_text VARCHAR(200),              -- e.g., "within 6 months", "by 17 February 2024"
    deadline_date DATE,                      -- Parsed absolute deadline (if applicable)
    deadline_relative VARCHAR(100),          -- Relative deadline (e.g., "6 months from designation")

    -- Criticality
    criticality VARCHAR(20) NOT NULL,        -- 'critical', 'important', 'recommended'
    penalty_info TEXT,                       -- Potential penalties for non-compliance

    -- Metadata
    keywords TEXT[],                         -- Searchable keywords
    related_requirements INTEGER[],          -- IDs of related requirements

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_criticality CHECK (criticality IN ('critical', 'important', 'recommended')),
    CONSTRAINT valid_obligation_type CHECK (obligation_type IN ('must', 'shall', 'should', 'may', 'prohibited'))
);

-- Indexes for law_requirements
CREATE INDEX idx_law_req_law ON law_requirements(law_id);
CREATE INDEX idx_law_req_cluster ON law_requirements(cluster_id);
CREATE INDEX idx_law_req_criticality ON law_requirements(criticality);
CREATE INDEX idx_law_req_deadline ON law_requirements(deadline_date);
CREATE INDEX idx_law_req_keywords ON law_requirements USING GIN(keywords);

-- ============================================================================
-- 2. COMPLIANCE ANALYSES TABLE
-- ============================================================================
-- Tracks user compliance check sessions

CREATE TABLE IF NOT EXISTS compliance_analyses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cluster_id INTEGER NOT NULL REFERENCES law_clusters(id) ON DELETE CASCADE,

    -- Analysis details
    analysis_name VARCHAR(200),              -- User-provided name (e.g., "Q4 2025 DSA Check")
    document_ids INTEGER[],                  -- IDs from user_documents table

    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'processing',  -- 'processing', 'completed', 'failed'

    -- Results summary
    total_requirements INTEGER,
    requirements_met INTEGER,
    requirements_partial INTEGER,
    requirements_gap INTEGER,

    -- Overall compliance score (0-100)
    compliance_score DECIMAL(5,2),

    -- Timing
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    -- Metadata
    analysis_params JSONB,                   -- Store analysis configuration

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_status CHECK (status IN ('processing', 'completed', 'failed', 'cancelled'))
);

-- Indexes for compliance_analyses
CREATE INDEX idx_compliance_user ON compliance_analyses(user_id);
CREATE INDEX idx_compliance_cluster ON compliance_analyses(cluster_id);
CREATE INDEX idx_compliance_status ON compliance_analyses(status);
CREATE INDEX idx_compliance_created ON compliance_analyses(created_at DESC);

-- ============================================================================
-- 3. GAP FINDINGS TABLE
-- ============================================================================
-- Stores individual gap analysis results (requirement by requirement)

CREATE TABLE IF NOT EXISTS gap_findings (
    id SERIAL PRIMARY KEY,
    analysis_id INTEGER NOT NULL REFERENCES compliance_analyses(id) ON DELETE CASCADE,
    requirement_id INTEGER NOT NULL REFERENCES law_requirements(id) ON DELETE CASCADE,

    -- Compliance status
    status VARCHAR(20) NOT NULL,             -- 'met', 'partial', 'gap', 'not_applicable'
    confidence_score DECIMAL(5,2),           -- LLM confidence in assessment (0-100)

    -- Evidence
    evidence_text TEXT,                      -- Quote from user document that addresses this
    evidence_source VARCHAR(500),            -- Document name + page/section

    -- Gap details
    gap_description TEXT,                    -- What's missing/incomplete
    recommendation TEXT,                     -- Specific action to take

    -- Action plan
    priority INTEGER,                        -- 1-5 (1=highest based on criticality + deadline)
    estimated_effort VARCHAR(50),            -- 'quick', 'moderate', 'significant'
    action_owner VARCHAR(200),               -- Suggested role (e.g., "Legal team", "DPO")

    -- Semantic matching details (for debugging)
    similarity_score DECIMAL(5,4),           -- Cosine similarity from semantic search
    matched_chunks TEXT[],                   -- Document chunks that matched

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_gap_status CHECK (status IN ('met', 'partial', 'gap', 'not_applicable')),
    CONSTRAINT valid_priority CHECK (priority BETWEEN 1 AND 5)
);

-- Indexes for gap_findings
CREATE INDEX idx_gap_analysis ON gap_findings(analysis_id);
CREATE INDEX idx_gap_requirement ON gap_findings(requirement_id);
CREATE INDEX idx_gap_status ON gap_findings(status);
CREATE INDEX idx_gap_priority ON gap_findings(priority);

-- ============================================================================
-- 4. COMPLIANCE ACTIONS TABLE
-- ============================================================================
-- Tracks user progress on resolving gaps

CREATE TABLE IF NOT EXISTS compliance_actions (
    id SERIAL PRIMARY KEY,
    gap_finding_id INTEGER NOT NULL REFERENCES gap_findings(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Action details
    action_title VARCHAR(200) NOT NULL,
    action_description TEXT,

    -- Status tracking
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- 'pending', 'in_progress', 'completed', 'cancelled'

    -- Assignment
    assigned_to VARCHAR(200),                -- Person/team responsible
    due_date DATE,

    -- Resolution
    resolution_notes TEXT,                   -- How the gap was resolved
    evidence_document_id INTEGER,            -- Updated document proving compliance

    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    CONSTRAINT valid_action_status CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled'))
);

-- Indexes for compliance_actions
CREATE INDEX idx_action_gap ON compliance_actions(gap_finding_id);
CREATE INDEX idx_action_user ON compliance_actions(user_id);
CREATE INDEX idx_action_status ON compliance_actions(status);
CREATE INDEX idx_action_due ON compliance_actions(due_date);

-- ============================================================================
-- 5. REQUIREMENT EMBEDDINGS TABLE
-- ============================================================================
-- Stores vector embeddings for semantic search

CREATE TABLE IF NOT EXISTS requirement_embeddings (
    id SERIAL PRIMARY KEY,
    requirement_id INTEGER NOT NULL REFERENCES law_requirements(id) ON DELETE CASCADE,

    -- Embedding
    embedding vector(1536),                  -- OpenAI text-embedding-3-large dimension
    embedding_model VARCHAR(100),            -- Model used (for versioning)

    -- Text that was embedded
    embedded_text TEXT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_requirement_embedding UNIQUE (requirement_id, embedding_model)
);

-- Vector similarity index (requires pgvector extension)
-- Uncomment if pgvector is installed:
-- CREATE INDEX idx_req_embedding ON requirement_embeddings USING ivfflat (embedding vector_cosine_ops);

-- ============================================================================
-- 6. ANALYSIS EXPORTS TABLE
-- ============================================================================
-- Tracks exported compliance reports

CREATE TABLE IF NOT EXISTS analysis_exports (
    id SERIAL PRIMARY KEY,
    analysis_id INTEGER NOT NULL REFERENCES compliance_analyses(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Export details
    export_format VARCHAR(20) NOT NULL,      -- 'docx', 'pdf', 'json'
    file_path TEXT,                          -- Storage path
    file_size_bytes INTEGER,

    -- Access
    download_count INTEGER DEFAULT 0,
    last_downloaded_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,                    -- Optional expiration

    CONSTRAINT valid_export_format CHECK (export_format IN ('docx', 'pdf', 'json', 'csv'))
);

-- Indexes for analysis_exports
CREATE INDEX idx_export_analysis ON analysis_exports(analysis_id);
CREATE INDEX idx_export_user ON analysis_exports(user_id);
CREATE INDEX idx_export_created ON analysis_exports(created_at DESC);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to update compliance score
CREATE OR REPLACE FUNCTION update_compliance_score()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE compliance_analyses
    SET
        requirements_met = (
            SELECT COUNT(*) FROM gap_findings
            WHERE analysis_id = NEW.analysis_id AND status = 'met'
        ),
        requirements_partial = (
            SELECT COUNT(*) FROM gap_findings
            WHERE analysis_id = NEW.analysis_id AND status = 'partial'
        ),
        requirements_gap = (
            SELECT COUNT(*) FROM gap_findings
            WHERE analysis_id = NEW.analysis_id AND status = 'gap'
        ),
        total_requirements = (
            SELECT COUNT(*) FROM gap_findings
            WHERE analysis_id = NEW.analysis_id AND status != 'not_applicable'
        ),
        compliance_score = CASE
            WHEN (SELECT COUNT(*) FROM gap_findings WHERE analysis_id = NEW.analysis_id AND status != 'not_applicable') = 0
            THEN NULL
            ELSE (
                (
                    (SELECT COUNT(*) FROM gap_findings WHERE analysis_id = NEW.analysis_id AND status = 'met') * 100.0 +
                    (SELECT COUNT(*) FROM gap_findings WHERE analysis_id = NEW.analysis_id AND status = 'partial') * 50.0
                ) /
                (SELECT COUNT(*) FROM gap_findings WHERE analysis_id = NEW.analysis_id AND status != 'not_applicable')
            )
        END,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.analysis_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update compliance scores
CREATE TRIGGER update_compliance_score_trigger
AFTER INSERT OR UPDATE OR DELETE ON gap_findings
FOR EACH ROW
EXECUTE FUNCTION update_compliance_score();

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- View: User's recent compliance analyses with summary
CREATE OR REPLACE VIEW user_compliance_summary AS
SELECT
    ca.id,
    ca.user_id,
    ca.analysis_name,
    lc.name as cluster_name,
    lc.policy_area,
    ca.status,
    ca.compliance_score,
    ca.requirements_met,
    ca.requirements_partial,
    ca.requirements_gap,
    ca.total_requirements,
    ca.created_at,
    ca.completed_at,
    CASE
        WHEN ca.compliance_score >= 90 THEN 'excellent'
        WHEN ca.compliance_score >= 70 THEN 'good'
        WHEN ca.compliance_score >= 50 THEN 'needs_improvement'
        ELSE 'critical'
    END as compliance_rating
FROM compliance_analyses ca
JOIN law_clusters lc ON ca.cluster_id = lc.id
ORDER BY ca.created_at DESC;

-- View: Critical gaps by cluster (for dashboard)
CREATE OR REPLACE VIEW critical_gaps_summary AS
SELECT
    lc.id as cluster_id,
    lc.name as cluster_name,
    COUNT(DISTINCT gf.id) as critical_gap_count,
    COUNT(DISTINCT ca.user_id) as affected_users,
    string_agg(DISTINCT lr.article_number, ', ' ORDER BY lr.article_number) as affected_articles
FROM law_clusters lc
JOIN compliance_analyses ca ON lc.id = ca.cluster_id
JOIN gap_findings gf ON ca.id = gf.analysis_id
JOIN law_requirements lr ON gf.requirement_id = lr.id
WHERE gf.status = 'gap'
  AND lr.criticality = 'critical'
  AND ca.status = 'completed'
GROUP BY lc.id, lc.name
ORDER BY critical_gap_count DESC;

-- ============================================================================
-- SAMPLE DATA FOR TESTING
-- ============================================================================
-- (Run this after requirements are extracted for a cluster)

-- Example: Insert a test requirement
-- INSERT INTO law_requirements (
--     law_id, cluster_id, article_number, requirement_text, requirement_summary,
--     obligation_type, applicable_to, deadline_text, criticality
-- ) VALUES (
--     1, 1, 'Article 15',
--     'Providers of intermediary services shall designate a single point of contact...',
--     'Designate EU point of contact',
--     'shall', 'All intermediary service providers',
--     'within 3 months of designation', 'critical'
-- );

-- ============================================================================
-- ROLLBACK SCRIPT (if needed)
-- ============================================================================
-- DROP VIEW IF EXISTS critical_gaps_summary CASCADE;
-- DROP VIEW IF EXISTS user_compliance_summary CASCADE;
-- DROP TRIGGER IF EXISTS update_compliance_score_trigger ON gap_findings CASCADE;
-- DROP FUNCTION IF EXISTS update_compliance_score() CASCADE;
-- DROP TABLE IF EXISTS analysis_exports CASCADE;
-- DROP TABLE IF EXISTS requirement_embeddings CASCADE;
-- DROP TABLE IF EXISTS compliance_actions CASCADE;
-- DROP TABLE IF EXISTS gap_findings CASCADE;
-- DROP TABLE IF EXISTS compliance_analyses CASCADE;
-- DROP TABLE IF EXISTS law_requirements CASCADE;

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
