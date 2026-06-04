-- 108_sync_runs_freshness.sql
-- Freshness tracking for the MEUB auto-sync layer. One row per sync run,
-- written by the cron tier endpoints. Powers the "Updated X ago" chip
-- (GET /api/sync/freshness), staleness detection, and the staleness email.
--
-- Supabase Data API grants are mandatory on new public.* tables
-- (CREATE TABLE -> ENABLE RLS -> CREATE POLICY -> GRANT). Public-read:
-- anon + authenticated SELECT, service_role ALL. The table holds no user
-- data; the backend writes it via the service role, the frontend reads
-- freshness through the API.

CREATE TABLE IF NOT EXISTS public.sync_runs (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key  text        NOT NULL,
    tier        text,
    status      text        NOT NULL,          -- 'success' | 'failed' | 'skipped'
    items_added integer,
    error       text,
    started_at  timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_sync_runs_source_started
    ON public.sync_runs (source_key, started_at DESC);

ALTER TABLE public.sync_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS sync_runs_read ON public.sync_runs;
CREATE POLICY sync_runs_read ON public.sync_runs
    FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS sync_runs_service_all ON public.sync_runs;
CREATE POLICY sync_runs_service_all ON public.sync_runs
    FOR ALL TO service_role USING (true) WITH CHECK (true);

GRANT SELECT ON public.sync_runs TO anon, authenticated;
GRANT ALL ON public.sync_runs TO service_role;
