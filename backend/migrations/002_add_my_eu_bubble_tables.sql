-- Migration: Add My EU Bubble tables
-- Date: 2025-11-08
-- Description: Creates tables for RSS feed subscriptions, read tracking, and saved entries for My EU Bubble feature

-- ============================================================================
-- User Feed Subscriptions
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_feed_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    feed_id UUID NOT NULL REFERENCES rss_feeds(id) ON DELETE CASCADE,

    -- Subscription settings
    is_active BOOLEAN DEFAULT TRUE,
    notification_enabled BOOLEAN DEFAULT FALSE,

    -- Timestamps
    subscribed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    last_viewed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    -- Unique constraint: one subscription per user per feed
    CONSTRAINT uq_user_feed_subscription UNIQUE (user_id, feed_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_feed_subscriptions_user_id ON user_feed_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_feed_subscriptions_feed_id ON user_feed_subscriptions(feed_id);
CREATE INDEX IF NOT EXISTS idx_user_feed_subscriptions_active ON user_feed_subscriptions(user_id, is_active);

-- Comments
COMMENT ON TABLE user_feed_subscriptions IS 'User subscriptions to RSS feeds for My EU Bubble';
COMMENT ON COLUMN user_feed_subscriptions.is_active IS 'Whether subscription is active (can be temporarily disabled)';
COMMENT ON COLUMN user_feed_subscriptions.notification_enabled IS 'Whether to notify user about new entries';


-- ============================================================================
-- User Feed Reads
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_feed_reads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rss_entry_id UUID NOT NULL REFERENCES rss_entries(id) ON DELETE CASCADE,

    -- Reading metrics
    reading_time_seconds INTEGER,
    read_count INTEGER DEFAULT 1,
    clicked_link BOOLEAN DEFAULT FALSE,

    -- Timestamps
    first_read_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    last_read_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    -- Unique constraint: one read record per user per entry
    CONSTRAINT uq_user_entry_read UNIQUE (user_id, rss_entry_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_feed_reads_user_id ON user_feed_reads(user_id);
CREATE INDEX IF NOT EXISTS idx_user_feed_reads_entry_id ON user_feed_reads(rss_entry_id);
CREATE INDEX IF NOT EXISTS idx_user_feed_reads_last_read ON user_feed_reads(user_id, last_read_at DESC);

-- Comments
COMMENT ON TABLE user_feed_reads IS 'Track which RSS entries users have read';
COMMENT ON COLUMN user_feed_reads.reading_time_seconds IS 'Time spent reading entry in seconds';
COMMENT ON COLUMN user_feed_reads.read_count IS 'Number of times user opened this entry';
COMMENT ON COLUMN user_feed_reads.clicked_link IS 'Whether user clicked through to source';


-- ============================================================================
-- User Saved Entries
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_saved_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rss_entry_id UUID NOT NULL REFERENCES rss_entries(id) ON DELETE CASCADE,

    -- User annotations
    notes TEXT,
    tags TEXT[],
    collection_name VARCHAR(100),

    -- Priority/reminder
    is_starred BOOLEAN DEFAULT FALSE,
    reminder_at TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    saved_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    last_viewed_at TIMESTAMP WITH TIME ZONE,

    -- Unique constraint: one saved record per user per entry
    CONSTRAINT uq_user_saved_entry UNIQUE (user_id, rss_entry_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_saved_entries_user_id ON user_saved_entries(user_id);
CREATE INDEX IF NOT EXISTS idx_user_saved_entries_entry_id ON user_saved_entries(rss_entry_id);
CREATE INDEX IF NOT EXISTS idx_user_saved_entries_collection ON user_saved_entries(user_id, collection_name);
CREATE INDEX IF NOT EXISTS idx_user_saved_entries_starred ON user_saved_entries(user_id, is_starred);
CREATE INDEX IF NOT EXISTS idx_user_saved_entries_tags ON user_saved_entries USING GIN (tags);

-- Comments
COMMENT ON TABLE user_saved_entries IS 'User bookmarked/saved RSS entries for My EU Bubble';
COMMENT ON COLUMN user_saved_entries.notes IS 'Personal notes about this entry';
COMMENT ON COLUMN user_saved_entries.tags IS 'User-defined tags for organization';
COMMENT ON COLUMN user_saved_entries.collection_name IS 'Collection/folder name for grouping';
COMMENT ON COLUMN user_saved_entries.is_starred IS 'Mark as important/starred';


-- ============================================================================
-- Update Functions
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
DROP TRIGGER IF EXISTS update_user_feed_subscriptions_updated_at ON user_feed_subscriptions;
CREATE TRIGGER update_user_feed_subscriptions_updated_at
    BEFORE UPDATE ON user_feed_subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_saved_entries_updated_at ON user_saved_entries;
CREATE TRIGGER update_user_saved_entries_updated_at
    BEFORE UPDATE ON user_saved_entries
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- Grants (adjust based on your database user configuration)
-- ============================================================================

-- Grant permissions to authenticated users (adjust role name as needed)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON user_feed_subscriptions TO authenticated;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON user_feed_reads TO authenticated;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON user_saved_entries TO authenticated;
