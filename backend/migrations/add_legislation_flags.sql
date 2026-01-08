-- Migration: Add Legislation Classification Flags
-- Description: Distinguish primary legislation from annexes and technical documents
-- Date: 2025-11-14

-- Add is_primary_legislation flag
ALTER TABLE eu_laws ADD COLUMN is_primary_legislation BOOLEAN DEFAULT TRUE;

-- Add parent_law_uuid for annexes (to link to parent legislation)
ALTER TABLE eu_laws ADD COLUMN parent_law_uuid VARCHAR(36);

-- Add foreign key constraint
ALTER TABLE eu_laws ADD CONSTRAINT fk_parent_law
    FOREIGN KEY (parent_law_uuid) REFERENCES eu_laws(uuid) ON DELETE CASCADE;

-- Create index for parent relationships
CREATE INDEX idx_eu_laws_parent ON eu_laws(parent_law_uuid);

-- Update existing records: Mark annexes and OJ ToCs as non-primary
UPDATE eu_laws
SET is_primary_legislation = FALSE
WHERE doc_type ILIKE '%ANNEX%'
   OR doc_type ILIKE '%Official Journal%'
   OR doc_type ILIKE '%Table of Contents%'
   OR title ILIKE 'ANNEX%';

-- Add index for filtering
CREATE INDEX idx_eu_laws_primary ON eu_laws(is_primary_legislation);

-- Add comments
COMMENT ON COLUMN eu_laws.is_primary_legislation IS 'TRUE for regulations/directives/decisions, FALSE for annexes/ToCs';
COMMENT ON COLUMN eu_laws.parent_law_uuid IS 'UUID of parent law for annexes and amendments';
