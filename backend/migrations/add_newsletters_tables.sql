-- Add EC Newsletter tracking tables
-- Required for European Commission newsletter intelligence system

-- Newsletter sources (DGs and their newsletters)
CREATE TABLE IF NOT EXISTS newsletters_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dg_name VARCHAR(100) NOT NULL,
    newsletter_name VARCHAR(200) NOT NULL,
    dg_code VARCHAR(50) NOT NULL, -- e.g., 'clima', 'comp', 'sante'
    service_id VARCHAR(50), -- EC Newsroom service ID
    subscription_url TEXT,
    archive_url TEXT,
    ingestion_method VARCHAR(20) CHECK (ingestion_method IN ('rss', 'scrape', 'api')),
    rss_feed_url TEXT,
    publication_frequency VARCHAR(50), -- 'weekly', 'monthly', 'quarterly'
    strategic_tier VARCHAR(10) CHECK (strategic_tier IN ('tier1', 'tier2', 'tier3')),
    is_active BOOLEAN DEFAULT true,
    last_scraped_at TIMESTAMP,
    scrape_interval_hours INTEGER DEFAULT 24,
    source_metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(dg_code, service_id)
);

-- Newsletter content items
CREATE TABLE IF NOT EXISTS newsletters_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES newsletters_sources(id) ON DELETE CASCADE,
    publication_date TIMESTAMP NOT NULL,
    retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    title TEXT NOT NULL,
    summary TEXT,
    full_content TEXT,
    content_type VARCHAR(50), -- 'article', 'consultation', 'event', 'funding', 'general'
    language VARCHAR(10) DEFAULT 'en',
    original_url TEXT,
    content_fingerprint VARCHAR(64) UNIQUE, -- SHA-256 hash for deduplication
    topics TEXT[], -- Simple text array for topics/policy areas
    entities JSONB, -- Extracted entities (regulations, directives, people, etc.)
    content_metadata JSONB, -- Flexible field for additional data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User newsletter preferences
CREATE TABLE IF NOT EXISTS user_newsletter_preferences (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    source_id UUID REFERENCES newsletters_sources(id) ON DELETE CASCADE,
    is_subscribed BOOLEAN DEFAULT true,
    priority_weight FLOAT DEFAULT 1.0,
    notification_enabled BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, source_id)
);

-- User topic preferences (for filtering across all newsletters)
CREATE TABLE IF NOT EXISTS user_newsletter_topics (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    topic VARCHAR(100) NOT NULL,
    priority_weight FLOAT DEFAULT 1.0,
    notification_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, topic)
);

-- User interactions with newsletter content (for relevance feedback)
CREATE TABLE IF NOT EXISTS user_newsletter_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    content_id UUID REFERENCES newsletters_content(id) ON DELETE CASCADE,
    interaction_type VARCHAR(20) CHECK (interaction_type IN ('view', 'click', 'save', 'dismiss', 'feedback')),
    feedback_score INTEGER CHECK (feedback_score BETWEEN 1 AND 5), -- 1=not relevant, 5=highly relevant
    interaction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    interaction_metadata JSONB
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_newsletters_content_date ON newsletters_content(publication_date DESC);
CREATE INDEX IF NOT EXISTS idx_newsletters_content_fingerprint ON newsletters_content(content_fingerprint);
CREATE INDEX IF NOT EXISTS idx_newsletters_content_source ON newsletters_content(source_id, publication_date DESC);
CREATE INDEX IF NOT EXISTS idx_newsletters_content_topics ON newsletters_content USING gin(topics);
CREATE INDEX IF NOT EXISTS idx_newsletters_sources_active ON newsletters_sources(is_active, last_scraped_at);
CREATE INDEX IF NOT EXISTS idx_newsletters_sources_tier ON newsletters_sources(strategic_tier, is_active);
CREATE INDEX IF NOT EXISTS idx_user_newsletter_prefs ON user_newsletter_preferences(user_id, is_subscribed);
CREATE INDEX IF NOT EXISTS idx_user_newsletter_topics ON user_newsletter_topics(user_id);
CREATE INDEX IF NOT EXISTS idx_user_newsletter_interactions ON user_newsletter_interactions(user_id, content_id);

-- Comments for documentation
COMMENT ON TABLE newsletters_sources IS 'European Commission newsletter sources (DGs and agencies)';
COMMENT ON TABLE newsletters_content IS 'Parsed content from EC newsletters';
COMMENT ON TABLE user_newsletter_preferences IS 'User subscriptions to specific newsletters';
COMMENT ON TABLE user_newsletter_topics IS 'User topic preferences for filtering newsletter content';
COMMENT ON TABLE user_newsletter_interactions IS 'User interactions with newsletter content for relevance learning';

COMMENT ON COLUMN newsletters_sources.strategic_tier IS 'tier1=mission-critical, tier2=high-value sector-specific, tier3=specialized';
COMMENT ON COLUMN newsletters_content.content_fingerprint IS 'SHA-256 hash of title+summary for deduplication';
COMMENT ON COLUMN newsletters_content.content_type IS 'Categorization: consultation, event, funding, article, general';
