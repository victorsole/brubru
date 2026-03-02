-- Migration 027: Add pre_user_events table for funnel tracking + A/B testing
-- Tracks anonymous pre-user journey: page_load -> query_1 -> query_2 -> signup

CREATE TABLE IF NOT EXISTS pre_user_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pre_user_id VARCHAR(36) NOT NULL,
    event_type VARCHAR(30) NOT NULL,
    ab_variant VARCHAR(1) NOT NULL,
    event_metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pue_pre_user_id ON pre_user_events(pre_user_id);
CREATE INDEX IF NOT EXISTS idx_pue_event_type ON pre_user_events(event_type);
CREATE INDEX IF NOT EXISTS idx_pue_created_at ON pre_user_events(created_at);
