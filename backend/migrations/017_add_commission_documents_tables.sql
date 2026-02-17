-- Migration 017: Add Commission Documents Tables
-- Created: February 17, 2026
--
-- This migration creates tables for EC Register of Commission Documents
-- (COM, SWD, SEC, C, JOIN, OJ, PV):
-- - commission_documents: Main table for Commission documents
-- - user_commission_doc_tracks: User subscriptions to track documents

-- Create enum type (with duplicate guard)
DO $$ BEGIN
    CREATE TYPE commission_doc_type_enum AS ENUM (
        'COM', 'SWD', 'SEC', 'C', 'JOIN', 'OJ', 'PV'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Commission Documents table
CREATE TABLE IF NOT EXISTS commission_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identifiers
    reference VARCHAR NOT NULL UNIQUE,          -- e.g. "COM(2025) 87"
    title VARCHAR NOT NULL,

    -- Classification
    doc_type commission_doc_type_enum NOT NULL,

    -- Metadata
    publication_date TIMESTAMP,
    dg_responsible VARCHAR,                     -- DG code e.g. "CNECT"
    procedure_ref VARCHAR,                      -- OEIL cross-ref e.g. "2021/0106(COD)"
    languages VARCHAR[] DEFAULT '{}',
    portal_url VARCHAR,                         -- EUR-Lex or RegDoc URL
    celex VARCHAR,                              -- CELEX number for adopted acts

    -- Cross-references to legislative_carriages
    legislative_carriage_id UUID REFERENCES legislative_carriages(id) ON DELETE SET NULL,

    -- Temporal data
    scraped_at TIMESTAMP DEFAULT NOW(),
    first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes for commission_documents
CREATE INDEX IF NOT EXISTS ix_commission_documents_reference ON commission_documents(reference);
CREATE INDEX IF NOT EXISTS ix_commission_documents_doc_type ON commission_documents(doc_type);
CREATE INDEX IF NOT EXISTS ix_commission_documents_publication_date ON commission_documents(publication_date);
CREATE INDEX IF NOT EXISTS ix_commission_documents_procedure_ref ON commission_documents(procedure_ref);
CREATE INDEX IF NOT EXISTS ix_commission_documents_celex ON commission_documents(celex);
CREATE INDEX IF NOT EXISTS ix_commission_documents_legislative_carriage_id ON commission_documents(legislative_carriage_id);

-- User Commission Document Tracks table
CREATE TABLE IF NOT EXISTS user_commission_doc_tracks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    commission_document_id UUID NOT NULL REFERENCES commission_documents(id) ON DELETE CASCADE,

    -- Tracking metadata
    notify_on_new_documents BOOLEAN DEFAULT TRUE,
    tracked_since TIMESTAMP NOT NULL DEFAULT NOW(),
    notes TEXT,

    -- Unique constraint: user can only track each document once
    CONSTRAINT uq_user_commission_doc_track UNIQUE (user_id, commission_document_id)
);

-- Create indexes for user_commission_doc_tracks
CREATE INDEX IF NOT EXISTS ix_user_commission_doc_track_user_id ON user_commission_doc_tracks(user_id);
CREATE INDEX IF NOT EXISTS ix_user_commission_doc_track_doc_id ON user_commission_doc_tracks(commission_document_id);

-- Add comments
COMMENT ON TABLE commission_documents IS 'EC Register of Commission Documents (COM, SWD, SEC, C, JOIN, OJ, PV)';
COMMENT ON TABLE user_commission_doc_tracks IS 'User subscriptions to track specific Commission documents';
