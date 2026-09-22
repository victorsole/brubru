-- 235: say WHERE a sync run happened (22 Sep 2026).
--
-- Why: sync_runs has source_key, tier, status, items_added, error and the two timestamps,
-- and nothing that separates a Railway container from a laptop. So a developer running a
-- script locally writes into the same ledger the production health endpoint reads. It
-- happened today: two local runs (a script edited mid-session, and a removal guard firing
-- exactly as designed during a manual catch-up) put the daily tier at `healthy: false`
-- with a 33% failure rate while nothing in the container had failed.
--
-- `runner` is filled by services/sync/freshness.record_run from the environment:
-- 'railway' inside the container, 'local' otherwise, overridable with BRUBRU_RUNNER.
-- Existing rows stay NULL, which means "written before this column existed" and is
-- counted as before; only rows known to be local are marked.

ALTER TABLE public.sync_runs ADD COLUMN IF NOT EXISTS runner text;

CREATE INDEX IF NOT EXISTS ix_sync_runs_runner_started
    ON public.sync_runs (runner, started_at DESC);

COMMENT ON COLUMN public.sync_runs.runner IS
    'Where the run executed: railway | local | NULL (before 22 Sep 2026). The health '
    'endpoint judges tiers on container runs only.';

-- The two local runs of 22 Sep 2026 that dragged the daily tier down.
UPDATE public.sync_runs
   SET runner = 'local'
 WHERE runner IS NULL
   AND started_at::date = DATE '2026-09-22'
   AND (source_key = 'live_register_snapshots'
        OR (source_key = 'who_is_who' AND status = 'failed'));
