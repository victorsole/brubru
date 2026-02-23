-- Migration 021: Add MEP Amendment Tables
-- Created: February 20, 2026
--
-- Two tables for EP committee amendment tracking:
-- - amendment_documents: Tracks fetched EP DOCX documents (AM, PR, etc.)
-- - mep_amendments: Individual parsed amendments with authors, groups, text diffs

-- Amendment Documents table
CREATE TABLE IF NOT EXISTS amendment_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identifiers
    procedure_reference VARCHAR NOT NULL,         -- e.g. "2023/0089(COD)"
    committee_code VARCHAR NOT NULL,              -- e.g. "JURI"
    pe_reference VARCHAR NOT NULL UNIQUE,         -- e.g. "PE753.448"
    document_type VARCHAR NOT NULL DEFAULT 'AM',  -- AM, PR, RD, etc.

    -- Metadata
    document_date TIMESTAMP,
    doceo_url VARCHAR,
    rapporteur_name VARCHAR,
    total_amendments INTEGER DEFAULT 0,

    -- Processing status
    status VARCHAR NOT NULL DEFAULT 'pending',    -- pending, fetched, parsed, failed
    error_message TEXT,

    -- Temporal
    scraped_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for amendment_documents
CREATE INDEX IF NOT EXISTS ix_amendment_documents_procedure ON amendment_documents(procedure_reference);
CREATE INDEX IF NOT EXISTS ix_amendment_documents_committee ON amendment_documents(committee_code);
CREATE INDEX IF NOT EXISTS ix_amendment_documents_status ON amendment_documents(status);

-- MEP Amendments table
CREATE TABLE IF NOT EXISTS mep_amendments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Document reference
    procedure_reference VARCHAR NOT NULL,
    committee_code VARCHAR NOT NULL,
    pe_reference VARCHAR NOT NULL,
    amendment_number INTEGER NOT NULL,

    -- Authors
    author_names VARCHAR[] DEFAULT '{}',
    political_group VARCHAR,
    on_behalf_of_group BOOLEAN DEFAULT FALSE,
    mep_ids VARCHAR[] DEFAULT '{}',

    -- Element being amended
    element_type VARCHAR DEFAULT 'unknown',
    element_number VARCHAR DEFAULT '',
    element_reference VARCHAR DEFAULT '',

    -- Amendment content
    amendment_type VARCHAR DEFAULT 'modification',  -- modification, suppression, addition
    original_text TEXT DEFAULT '',
    proposed_text TEXT DEFAULT '',
    justification TEXT,

    -- Metadata
    original_language VARCHAR DEFAULT 'en',
    source_url VARCHAR,
    source_format VARCHAR DEFAULT 'docx',
    parsing_confidence FLOAT DEFAULT 1.0,
    document_date TIMESTAMP,

    -- Temporal
    scraped_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Unique constraint: one amendment per document
    CONSTRAINT uq_mep_amendment_pe_num UNIQUE (pe_reference, amendment_number)
);

-- Indexes for mep_amendments
CREATE INDEX IF NOT EXISTS ix_mep_amendments_procedure ON mep_amendments(procedure_reference);
CREATE INDEX IF NOT EXISTS ix_mep_amendments_committee ON mep_amendments(committee_code);
CREATE INDEX IF NOT EXISTS ix_mep_amendments_pe_ref ON mep_amendments(pe_reference);
CREATE INDEX IF NOT EXISTS ix_mep_amendments_group ON mep_amendments(political_group);
CREATE INDEX IF NOT EXISTS ix_mep_amendments_element_type ON mep_amendments(element_type);
CREATE INDEX IF NOT EXISTS ix_mep_amendments_amendment_type ON mep_amendments(amendment_type);
CREATE INDEX IF NOT EXISTS ix_mep_amendments_number ON mep_amendments(amendment_number);

-- Comments
COMMENT ON TABLE amendment_documents IS 'EP committee amendment documents (AM, PR) fetched from doceo';
COMMENT ON TABLE mep_amendments IS 'Individual parsed MEP amendments with authors, groups, and text diffs';
