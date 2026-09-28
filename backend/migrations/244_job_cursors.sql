-- 244: a resume cursor for long drains that cannot finish in one run.
--
-- `backfill_eu_comitology.py` walks the Commission register from page 0 on every run and is
-- killed by the 900-second timeout at roughly page 120. It therefore re-read the same ~12,000
-- documents three runs a day and never reached the tail: 95,461 of 115,206 documents are
-- stored, and the missing ~19,700 sit on pages the job has never once visited. Raising the
-- timeout does not fix a job that always starts at the beginning.
--
-- Deliberately generic: any bounded drain can keep its place here, keyed by job name, so the
-- next one does not invent its own table. See memory/feedback_a_window_job_never_reaches_the_backlog.
CREATE TABLE IF NOT EXISTS public.job_cursors (
    job_key      TEXT PRIMARY KEY,
    cursor_value TEXT        NOT NULL,
    note         TEXT,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.job_cursors IS
    'Where a long-running drain got to, so the next run continues instead of restarting. '
    'cursor_value is text so a job can store a page number, an id or a date without a schema change.';
COMMENT ON COLUMN public.job_cursors.cursor_value IS
    'Job-defined. backfill_eu_comitology stores the next page number to read, wrapping to 0 '
    'at the end of the register so new documents at the head are picked up again.';

ALTER TABLE public.job_cursors ENABLE ROW LEVEL SECURITY;

-- Internal bookkeeping only: no anon/authenticated access. The service role writes it and
-- the drains read it server-side.
DROP POLICY IF EXISTS job_cursors_service_all ON public.job_cursors;
CREATE POLICY job_cursors_service_all ON public.job_cursors
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Explicit grants are mandatory on new public.* tables: the default grant was removed
-- 30 Oct 2026, so a replay (staging spin-up, restore, new env) breaks without these.
-- See memory/feedback_supabase_data_api_grants.md.
GRANT ALL ON public.job_cursors TO service_role;
