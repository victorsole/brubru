-- Migration 031: Daily EU Briefs
-- Stores scraped EU news headlines for the Daily EU Brief feature
-- Created: March 2026

CREATE TABLE IF NOT EXISTS daily_briefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brief_date DATE NOT NULL,
    headline TEXT NOT NULL,
    url TEXT NOT NULL,
    source VARCHAR(100) NOT NULL,
    category VARCHAR(20) NOT NULL DEFAULT 'ec',
    priority INTEGER NOT NULL DEFAULT 99,
    snippet TEXT,
    suggested_query TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_daily_briefs_date ON daily_briefs(brief_date);
CREATE INDEX IF NOT EXISTS ix_daily_briefs_date_priority ON daily_briefs(brief_date, priority);

-- Prevent duplicate headlines on the same date
CREATE UNIQUE INDEX IF NOT EXISTS uq_daily_briefs_date_url ON daily_briefs(brief_date, url);

COMMENT ON TABLE daily_briefs IS 'Daily EU institutional news headlines for the chat Daily Brief feature';
