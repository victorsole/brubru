-- Migration: Add missing columns to eu_laws table
-- Description: Add is_primary_legislation and parent_law_uuid columns
-- Date: 2026-01-02

-- Add columns if they don't exist
DO $$
BEGIN
    -- Add is_primary_legislation column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'eu_laws' AND column_name = 'is_primary_legislation'
    ) THEN
        ALTER TABLE eu_laws ADD COLUMN is_primary_legislation BOOLEAN DEFAULT TRUE;
        CREATE INDEX idx_eu_laws_is_primary ON eu_laws(is_primary_legislation);
        RAISE NOTICE 'Added is_primary_legislation column';
    ELSE
        RAISE NOTICE 'is_primary_legislation column already exists';
    END IF;

    -- Add parent_law_uuid column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'eu_laws' AND column_name = 'parent_law_uuid'
    ) THEN
        ALTER TABLE eu_laws ADD COLUMN parent_law_uuid VARCHAR(36);
        CREATE INDEX idx_eu_laws_parent ON eu_laws(parent_law_uuid);
        RAISE NOTICE 'Added parent_law_uuid column';
    ELSE
        RAISE NOTICE 'parent_law_uuid column already exists';
    END IF;

    -- Add cluster_id column to law_requirements if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'law_requirements' AND column_name = 'cluster_id'
    ) THEN
        ALTER TABLE law_requirements ADD COLUMN cluster_id INTEGER;
        CREATE INDEX idx_law_requirements_cluster ON law_requirements(cluster_id);
        RAISE NOTICE 'Added cluster_id column to law_requirements';
    ELSE
        RAISE NOTICE 'cluster_id column already exists in law_requirements';
    END IF;
END $$;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Migration complete: eu_laws columns updated';
END $$;
