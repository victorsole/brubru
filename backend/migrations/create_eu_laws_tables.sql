-- Migration: Create EU Laws Tables
-- Description: Create tables for storing 50k+ EU laws from LEG_2025-11
-- Date: 2025-11-14

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing tables (if this is a re-run)
DROP TABLE IF EXISTS law_requirements CASCADE;
DROP TABLE IF EXISTS cluster_laws CASCADE;
DROP TABLE IF EXISTS law_clusters CASCADE;
DROP TABLE IF EXISTS eu_laws CASCADE;

-- Main EU Laws table
CREATE TABLE eu_laws (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) UNIQUE NOT NULL,
    celex VARCHAR(30),  -- Increased from 20
    doc_type TEXT,  -- TEXT - no length limit (some doc types are very long)
    title TEXT NOT NULL,
    date DATE,
    oj_reference VARCHAR(100),  -- Increased from 50
    policy_area VARCHAR(200),  -- Increased from 100
    legal_basis TEXT[],
    citations TEXT[],
    subject_matter TEXT[],
    xml_path TEXT NOT NULL,
    extra_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_eu_laws_uuid ON eu_laws(uuid);
CREATE INDEX idx_eu_laws_celex ON eu_laws(celex);
CREATE INDEX idx_eu_laws_policy_area ON eu_laws(policy_area);
CREATE INDEX idx_eu_laws_date ON eu_laws(date DESC);
CREATE INDEX idx_eu_laws_title ON eu_laws USING gin(to_tsvector('english', title));

-- Full-text search vector (generated column)
ALTER TABLE eu_laws ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(title, '') || ' ' ||
            coalesce(celex, '') || ' ' ||
            coalesce(doc_type, '')
        )
    ) STORED;

CREATE INDEX idx_eu_laws_search_vector ON eu_laws USING GIN(search_vector);

-- Law Clusters table (for EU Law Comply feature)
CREATE TABLE law_clusters (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    primary_law_id INTEGER,
    description TEXT,
    applicability TEXT,
    policy_area VARCHAR(100),
    priority_level VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_law_clusters_policy_area ON law_clusters(policy_area);
CREATE INDEX idx_law_clusters_priority ON law_clusters(priority_level);

-- Cluster-Law relationships (many-to-many)
CREATE TABLE cluster_laws (
    cluster_id INTEGER NOT NULL,
    law_id INTEGER NOT NULL,
    relationship_type VARCHAR(50),
    PRIMARY KEY (cluster_id, law_id),
    FOREIGN KEY (cluster_id) REFERENCES law_clusters(id) ON DELETE CASCADE,
    FOREIGN KEY (law_id) REFERENCES eu_laws(id) ON DELETE CASCADE
);

CREATE INDEX idx_cluster_laws_cluster ON cluster_laws(cluster_id);
CREATE INDEX idx_cluster_laws_law ON cluster_laws(law_id);

-- Law Requirements table (for compliance checking)
CREATE TABLE law_requirements (
    id SERIAL PRIMARY KEY,
    law_id INTEGER NOT NULL,
    article VARCHAR(50),
    requirement_text TEXT NOT NULL,
    deadline DATE,
    criticality VARCHAR(20),
    applicable_entity VARCHAR(100),
    extra_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (law_id) REFERENCES eu_laws(id) ON DELETE CASCADE
);

CREATE INDEX idx_law_requirements_law_id ON law_requirements(law_id);
CREATE INDEX idx_law_requirements_criticality ON law_requirements(criticality);
CREATE INDEX idx_law_requirements_deadline ON law_requirements(deadline);

-- Update trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_eu_laws_updated_at
    BEFORE UPDATE ON eu_laws
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE eu_laws IS 'EU legal documents from LEG_2025-11 directory (50k+ laws)';
COMMENT ON TABLE law_clusters IS 'Curated groups of related laws for compliance checking';
COMMENT ON TABLE cluster_laws IS 'Relationships between laws and clusters';
COMMENT ON TABLE law_requirements IS 'Individual legal obligations extracted from laws';

COMMENT ON COLUMN eu_laws.uuid IS 'UUID from directory name in LEG_2025-11';
COMMENT ON COLUMN eu_laws.celex IS 'EU legal identifier (e.g., 32019D1194)';
COMMENT ON COLUMN eu_laws.policy_area IS 'One of 33 EU policy areas from eu_policies.json';
COMMENT ON COLUMN eu_laws.legal_basis IS 'Laws this document is based on';
COMMENT ON COLUMN eu_laws.citations IS 'Laws cited in this document';
COMMENT ON COLUMN eu_laws.search_vector IS 'Auto-generated full-text search vector';

-- Grant permissions (adjust based on your database user)
-- GRANT ALL PRIVILEGES ON TABLE eu_laws TO your_user;
-- GRANT ALL PRIVILEGES ON TABLE law_clusters TO your_user;
-- GRANT ALL PRIVILEGES ON TABLE cluster_laws TO your_user;
-- GRANT ALL PRIVILEGES ON TABLE law_requirements TO your_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO your_user;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'EU Laws tables created successfully!';
    RAISE NOTICE 'Tables: eu_laws, law_clusters, cluster_laws, law_requirements';
END $$;
