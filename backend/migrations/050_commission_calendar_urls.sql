-- Migration 050: Commission Calendar URL accumulator
-- Created: 2026-05-03
-- Purpose: Persist per-event detail URLs from the Commission's calendar RSS
-- feed. The feed is a 30-item global rolling window — items disappear from the
-- live feed within ~5-10 days, so older agenda items end up with detail_url=null.
-- This table accumulates everything we ever see, so once an event is captured
-- it stays available even after rolling out of RSS.
--
-- Populated on every call to /commissioners/{slug}/agenda (idempotent UPSERT
-- on (leader_id, event_date, title_normalised)).

CREATE TABLE IF NOT EXISTS public.commission_calendar_urls (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    leader_id          TEXT NOT NULL,                    -- COM_00006A3260A2 (political-leader authority ID)
    event_date         DATE NOT NULL,                    -- date as parsed from the RSS title
    title_normalised   TEXT NOT NULL,                    -- accent-stripped, lower-case, single-space
    title              TEXT NOT NULL,                    -- original RSS title (display)
    detail_url         TEXT NOT NULL,                    -- canonical /calendar/<slug>_en URL
    first_seen_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (leader_id, event_date, title_normalised)
);

CREATE INDEX IF NOT EXISTS idx_ccu_leader_date
    ON public.commission_calendar_urls (leader_id, event_date DESC);

CREATE INDEX IF NOT EXISTS idx_ccu_last_seen
    ON public.commission_calendar_urls (last_seen_at DESC);

ALTER TABLE public.commission_calendar_urls ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public read commission calendar urls" ON public.commission_calendar_urls;
CREATE POLICY "Public read commission calendar urls"
    ON public.commission_calendar_urls
    FOR SELECT
    USING (TRUE);
