-- Add AI enrichment fields to legislative_carriages table
-- Created: 2025-11-18
-- Purpose: Support AI analysis features for legislative files

ALTER TABLE legislative_carriages
ADD COLUMN IF NOT EXISTS ai_summary TEXT,
ADD COLUMN IF NOT EXISTS ai_entities JSON DEFAULT '[]'::json,
ADD COLUMN IF NOT EXISTS ai_policy_classifications JSON DEFAULT '[]'::json,
ADD COLUMN IF NOT EXISTS enriched_at TIMESTAMP;

-- Add index for querying enriched files
CREATE INDEX IF NOT EXISTS idx_legislative_carriages_ai_summary
ON legislative_carriages(ai_summary)
WHERE ai_summary IS NOT NULL;

-- Comment the new columns
COMMENT ON COLUMN legislative_carriages.ai_summary IS 'AI-generated summary in British English (Hugging Face)';
COMMENT ON COLUMN legislative_carriages.ai_entities IS 'Extracted entities (MEPs, committees, legislation) as JSON array';
COMMENT ON COLUMN legislative_carriages.ai_policy_classifications IS 'AI policy area classifications with confidence scores';
COMMENT ON COLUMN legislative_carriages.enriched_at IS 'Timestamp when AI enrichment was performed';
