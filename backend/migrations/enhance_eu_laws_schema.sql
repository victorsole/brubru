-- Great Regulatory Scan: Phase 2A - Schema Enhancement
-- Adds derived CELEX fields, doc_type normalization, corpus management columns
-- Run via Supabase SQL Editor

-- CELEX-derived fields (computed once from CELEX string, queried often)
ALTER TABLE eu_laws ADD COLUMN IF NOT EXISTS celex_year INTEGER;
ALTER TABLE eu_laws ADD COLUMN IF NOT EXISTS celex_type CHAR(1);
ALTER TABLE eu_laws ADD COLUMN IF NOT EXISTS celex_number INTEGER;

-- Normalized document type (10 clean categories instead of ~150 raw values)
ALTER TABLE eu_laws ADD COLUMN IF NOT EXISTS doc_type_normalized VARCHAR(50);

-- Corpus management (for delta imports and version tracking)
ALTER TABLE eu_laws ADD COLUMN IF NOT EXISTS corpus_version VARCHAR(20) DEFAULT 'LEG_2025-11';
ALTER TABLE eu_laws ADD COLUMN IF NOT EXISTS corpus_status VARCHAR(20) DEFAULT 'active';
ALTER TABLE eu_laws ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);

-- Indexes for new columns
CREATE INDEX IF NOT EXISTS idx_eu_laws_celex_year ON eu_laws(celex_year);
CREATE INDEX IF NOT EXISTS idx_eu_laws_doc_type_norm ON eu_laws(doc_type_normalized);
CREATE INDEX IF NOT EXISTS idx_eu_laws_corpus_status ON eu_laws(corpus_status);
CREATE INDEX IF NOT EXISTS idx_eu_laws_corpus_version ON eu_laws(corpus_version);

-- Set defaults for existing rows
UPDATE eu_laws SET corpus_version = 'LEG_2025-11' WHERE corpus_version IS NULL;
UPDATE eu_laws SET corpus_status = 'active' WHERE corpus_status IS NULL;
