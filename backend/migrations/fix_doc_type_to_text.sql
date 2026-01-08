-- Migration: Change doc_type to TEXT
-- Description: Some document types are longer than 500 chars, use unlimited TEXT
-- Date: 2025-11-14

-- Step 1: Drop the generated column and its index
DROP INDEX IF EXISTS idx_eu_laws_search_vector;
ALTER TABLE eu_laws DROP COLUMN IF EXISTS search_vector;

-- Step 2: Change doc_type to TEXT (unlimited length)
ALTER TABLE eu_laws ALTER COLUMN doc_type TYPE TEXT;

-- Step 3: Recreate the generated column
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

-- Add comment
COMMENT ON COLUMN eu_laws.doc_type IS 'Document type from Formex XML (TEXT - unlimited length)';
