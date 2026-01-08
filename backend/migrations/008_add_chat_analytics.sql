-- Migration: Add chat_analytics table for Phase E1 monitoring
-- Tracks per-message metrics for analytics dashboard

CREATE TABLE IF NOT EXISTS chat_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to message (nullable for flexibility)
    message_id UUID,
    conversation_id UUID,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Provider info
    provider TEXT NOT NULL,  -- 'Anthropic', 'OpenAI', 'Gemini'
    model TEXT NOT NULL,

    -- Performance metrics
    tokens_used INT DEFAULT 0,
    response_time_ms FLOAT DEFAULT 0,
    search_time_ms FLOAT DEFAULT 0,

    -- Quality signals
    had_knowledge_gap BOOLEAN DEFAULT FALSE,
    knowledge_gap_type TEXT,  -- 'legislation', 'procedure', 'mep', etc.
    source_tiers_used INT[],  -- Array of tiers used in response
    citation_count INT DEFAULT 0,

    -- Context info
    context_sources_count INT DEFAULT 0,
    query_length INT DEFAULT 0,
    response_length INT DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for analytics queries
CREATE INDEX IF NOT EXISTS idx_chat_analytics_created_at ON chat_analytics(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_analytics_provider ON chat_analytics(provider);
CREATE INDEX IF NOT EXISTS idx_chat_analytics_user_id ON chat_analytics(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_analytics_had_knowledge_gap ON chat_analytics(had_knowledge_gap);
CREATE INDEX IF NOT EXISTS idx_chat_analytics_conversation_id ON chat_analytics(conversation_id);

-- Date-based partitioning hint (for future optimization)
CREATE INDEX IF NOT EXISTS idx_chat_analytics_date ON chat_analytics(DATE(created_at));

-- Comment for documentation
COMMENT ON TABLE chat_analytics IS 'Per-message analytics for monitoring dashboard (Phase E1)';
COMMENT ON COLUMN chat_analytics.provider IS 'AI provider: Anthropic, OpenAI, or Gemini';
COMMENT ON COLUMN chat_analytics.source_tiers_used IS 'Array of source tiers (1-5) used in citations';
COMMENT ON COLUMN chat_analytics.had_knowledge_gap IS 'True if AI responded with uncertainty';
