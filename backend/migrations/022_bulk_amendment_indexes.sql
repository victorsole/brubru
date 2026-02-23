-- Migration 022: Bulk Amendment Indexes + EP Open Data Identifier
-- Created: February 2026
--
-- Adds:
-- 1. ep_identifier column to amendment_documents for EP Open Data dedup
-- 2. GIN index on mep_amendments.author_names for fast MEP name search
-- 3. Composite index for MEP-across-procedures queries

-- EP Open Data identifier for dedup (e.g. "LIBE-AM-779775")
ALTER TABLE amendment_documents ADD COLUMN IF NOT EXISTS ep_identifier VARCHAR(100);
CREATE UNIQUE INDEX IF NOT EXISTS ix_amendment_documents_ep_identifier
    ON amendment_documents(ep_identifier) WHERE ep_identifier IS NOT NULL;

-- GIN index for fast MEP name search across all amendments
-- Enables: WHERE author_names @> ARRAY['Axel Voss']
CREATE INDEX IF NOT EXISTS ix_mep_amendments_author_names_gin
    ON mep_amendments USING GIN (author_names);

-- Composite index for MEP-across-procedures queries
CREATE INDEX IF NOT EXISTS ix_mep_amendments_group_procedure
    ON mep_amendments(political_group, procedure_reference);

-- Comments
COMMENT ON COLUMN amendment_documents.ep_identifier IS 'EP Open Data API identifier for bulk sync dedup';
