-- 218_scraper_health_state.sql
-- Persistent state for the nightly scraper-health detector (scripts/scraper_health.py
-- + POST /api/cron/scraper-health). One row per registered (body_code, item_type)
-- scraper. consecutive_fails lets the cron alert only when a scraper is BROKEN/ERROR
-- on N consecutive nightly runs (a single run can trip a source's rate limit and
-- false-positive), so >= 2 = confirmed break.

CREATE TABLE IF NOT EXISTS public.scraper_health_state (
    body_code         text        NOT NULL,
    item_type         text        NOT NULL,
    consecutive_fails integer      NOT NULL DEFAULT 0,
    last_status       text,
    rows_count        integer,
    last_parse        integer,
    detail            text,
    last_checked      timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (body_code, item_type)
);

ALTER TABLE public.scraper_health_state ENABLE ROW LEVEL SECURITY;

-- public read of fleet health; only service_role writes.
DROP POLICY IF EXISTS scraper_health_state_read ON public.scraper_health_state;
CREATE POLICY scraper_health_state_read ON public.scraper_health_state
    FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS scraper_health_state_service_all ON public.scraper_health_state;
CREATE POLICY scraper_health_state_service_all ON public.scraper_health_state
    FOR ALL TO service_role USING (true) WITH CHECK (true);

GRANT SELECT ON public.scraper_health_state TO anon, authenticated;
GRANT ALL    ON public.scraper_health_state TO service_role;

-- surface the currently-confirmed breaks fast.
CREATE INDEX IF NOT EXISTS idx_scraper_health_confirmed
    ON public.scraper_health_state (consecutive_fails) WHERE consecutive_fails >= 2;
