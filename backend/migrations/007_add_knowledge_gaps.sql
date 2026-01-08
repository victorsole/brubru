-- Migration: Add knowledge_gaps table for Phase C gap analysis
-- Tracks when the AI responds with "I don't know" to identify missing data

CREATE TABLE IF NOT EXISTS knowledge_gaps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Query information
    query TEXT NOT NULL,
    detected_topic TEXT,
    policy_area TEXT,

    -- Gap classification
    missing_data_type TEXT,  -- 'legislation', 'procedure', 'mep', 'date', 'statistic', 'document'

    -- Context
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    conversation_id TEXT,
    ai_response_excerpt TEXT,  -- First 500 chars of the "I don't know" response

    -- Analysis (filled after review)
    root_cause TEXT,  -- 'not_indexed', 'not_fetched', 'not_exists', 'outdated'
    resolution_notes TEXT,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for analysis queries
CREATE INDEX IF NOT EXISTS idx_knowledge_gaps_policy_area ON knowledge_gaps(policy_area);
CREATE INDEX IF NOT EXISTS idx_knowledge_gaps_missing_data_type ON knowledge_gaps(missing_data_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_gaps_created_at ON knowledge_gaps(created_at);
CREATE INDEX IF NOT EXISTS idx_knowledge_gaps_resolved ON knowledge_gaps(resolved);

-- Add trigger for updated_at
CREATE OR REPLACE FUNCTION update_knowledge_gaps_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_knowledge_gaps_updated_at ON knowledge_gaps;
CREATE TRIGGER trigger_knowledge_gaps_updated_at
    BEFORE UPDATE ON knowledge_gaps
    FOR EACH ROW
    EXECUTE FUNCTION update_knowledge_gaps_updated_at();

-- Comment for documentation
COMMENT ON TABLE knowledge_gaps IS 'Tracks AI "I don''t know" responses to identify knowledge base gaps (Phase C)';
COMMENT ON COLUMN knowledge_gaps.missing_data_type IS 'Type: legislation, procedure, mep, date, statistic, document';
COMMENT ON COLUMN knowledge_gaps.root_cause IS 'Cause: not_indexed, not_fetched, not_exists, outdated';
