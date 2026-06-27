-- 192_procedure_snapshots_source.sql
-- Phase 3, step 3.4 — distinguish measured daily rows from reconstructed history.
--
-- The daily writer (snapshot_source='daily') measures ALL five fast-signal counts live.
-- The OEIL-events bootstrap (snapshot_source='bootstrap') reconstructs the historical
-- PROCEDURAL-EVENT timeline (num_status_changes + timing) truthfully from oeil_key_events,
-- but the fast counts (amendments/documents/…) are NOT historically knowable, so they are
-- left 0 on bootstrap rows. This column lets a trajectory consumer filter to
-- snapshot_source='daily' for count-trajectories while still using every row for the
-- status/timing timeline — no fabricated count history.

ALTER TABLE public.procedure_snapshots
    ADD COLUMN IF NOT EXISTS snapshot_source TEXT NOT NULL DEFAULT 'daily';

CREATE INDEX IF NOT EXISTS idx_procedure_snapshots_source
    ON public.procedure_snapshots (snapshot_source);
