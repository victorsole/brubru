-- Migration 010: Add source field to legislative_carriages
-- Tracks where procedure data came from (Legislative Train, OEIL direct, EP Open Data)

-- Create enum type for carriage source
DO $$ BEGIN
    CREATE TYPE carriagesourceenum AS ENUM ('legislative_train', 'oeil_direct', 'ep_opendata');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Add source column with default value
ALTER TABLE legislative_carriages
ADD COLUMN IF NOT EXISTS source carriagesourceenum DEFAULT 'legislative_train';

-- Update existing records to have the default source
UPDATE legislative_carriages
SET source = 'legislative_train'
WHERE source IS NULL;

-- Create index for filtering by source
CREATE INDEX IF NOT EXISTS idx_carriages_source ON legislative_carriages(source);

-- Add comment explaining the field
COMMENT ON COLUMN legislative_carriages.source IS 'Data source: legislative_train (EC priorities), oeil_direct (OEIL procedures), ep_opendata (EP API)';
