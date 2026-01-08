-- Migration: Fix Column Sizes for EU Laws
-- Description: Increase VARCHAR limits for doc_type and policy_area
-- Date: 2025-11-14

-- Step 1: Drop the generated column and its index (they depend on doc_type and celex)
DROP INDEX IF EXISTS idx_eu_laws_search_vector;
ALTER TABLE eu_laws DROP COLUMN IF EXISTS search_vector;

-- Step 2: Increase column sizes
-- Increase doc_type from VARCHAR(100) to VARCHAR(500)
-- Some document types from Formex XML are very long
ALTER TABLE eu_laws ALTER COLUMN doc_type TYPE VARCHAR(500);

-- Increase policy_area from VARCHAR(100) to VARCHAR(200)
-- Policy area names can be longer than 100 chars
ALTER TABLE eu_laws ALTER COLUMN policy_area TYPE VARCHAR(200);

-- Increase oj_reference from VARCHAR(50) to VARCHAR(100)
-- Some OJ references are longer
ALTER TABLE eu_laws ALTER COLUMN oj_reference TYPE VARCHAR(100);

-- Increase celex from VARCHAR(20) to VARCHAR(30)
-- Some CELEX numbers might be longer
ALTER TABLE eu_laws ALTER COLUMN celex TYPE VARCHAR(30);

-- Step 3: Recreate the generated column with new types
ALTER TABLE eu_laws ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(title, '') || ' ' ||
            coalesce(celex, '') || ' ' ||
            coalesce(doc_type, '')
        )
    ) STORED;

-- Step 4: Recreate the index
CREATE INDEX idx_eu_laws_search_vector ON eu_laws USING GIN(search_vector);

-- Add comments
COMMENT ON COLUMN eu_laws.doc_type IS 'Document type from Formex XML (increased to 500 chars)';
COMMENT ON COLUMN eu_laws.policy_area IS 'EU policy area classification (increased to 200 chars)';
