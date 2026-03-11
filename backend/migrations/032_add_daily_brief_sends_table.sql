-- Track which emails have been sent the daily brief for a given date
-- Prevents duplicate sends on retries

CREATE TABLE IF NOT EXISTS daily_brief_sends (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    brief_date DATE NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_brief_sends_email_date
    ON daily_brief_sends (email, brief_date);

CREATE INDEX IF NOT EXISTS idx_daily_brief_sends_date
    ON daily_brief_sends (brief_date);
