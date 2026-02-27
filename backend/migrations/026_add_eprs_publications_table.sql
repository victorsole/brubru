-- Migration 026: Add EPRS Publications table
-- European Parliament Research Service publications (At a Glance, Briefings, In-Depth Analyses, Studies)
-- These serve as plain-language "jargon translators" for the chatbot -- no dedicated UI.
-- Created: 2026-02-27

-- Create enum type
DO $$ BEGIN
    CREATE TYPE eprs_publication_type_enum AS ENUM (
        'at_a_glance', 'briefing', 'in_depth_analysis',
        'study', 'blog_post', 'other'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create table
CREATE TABLE IF NOT EXISTS eprs_publications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core identifiers
    publication_id VARCHAR NOT NULL UNIQUE,  -- e.g. "EPRS_BRI(2024)762322"
    title VARCHAR NOT NULL,

    -- Classification
    publication_type eprs_publication_type_enum NOT NULL,

    -- URLs
    html_url VARCHAR,
    pdf_url VARCHAR,

    -- Publication metadata
    authors TEXT[] DEFAULT '{}',
    publication_date TIMESTAMP,

    -- Content
    summary TEXT,
    full_text TEXT,
    word_count INTEGER,
    page_count INTEGER,

    -- Legislative context (critical for chatbot matching)
    policy_areas TEXT[] DEFAULT '{}',
    committees TEXT[] DEFAULT '{}',
    related_celex_numbers TEXT[] DEFAULT '{}',
    related_procedures TEXT[] DEFAULT '{}',

    -- Categorization
    categories TEXT[] DEFAULT '{}',

    -- Quality metrics
    extraction_quality VARCHAR,
    has_full_text BOOLEAN DEFAULT FALSE,

    -- Temporal tracking
    scraped_at TIMESTAMP DEFAULT NOW(),
    first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for chatbot context builder queries
CREATE INDEX IF NOT EXISTS ix_eprs_publications_publication_id
    ON eprs_publications (publication_id);

CREATE INDEX IF NOT EXISTS ix_eprs_publications_publication_type
    ON eprs_publications (publication_type);

CREATE INDEX IF NOT EXISTS ix_eprs_publications_publication_date
    ON eprs_publications (publication_date);

-- GIN indexes for array containment queries (@> operator)
CREATE INDEX IF NOT EXISTS ix_eprs_publications_celex
    ON eprs_publications USING GIN (related_celex_numbers);

CREATE INDEX IF NOT EXISTS ix_eprs_publications_procedures
    ON eprs_publications USING GIN (related_procedures);

CREATE INDEX IF NOT EXISTS ix_eprs_publications_policy_areas
    ON eprs_publications USING GIN (policy_areas);
