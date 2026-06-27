-- 191_procedure_snapshots.sql
-- Phase 3, step 3.2 — the procedure-snapshot cube.
--
-- Append-only daily time-series: one row per legislative procedure (carriage) per day,
-- written by the Phase 3.3 daily job from services/snapshots/snapshot_builder.build_snapshot().
-- It records the procedure's SLOW state plus the 5 FAST-SIGNAL counts (amendments,
-- documents, committee work, lobby meetings, EPRS briefings) so the predictors can finally
-- see count-TRAJECTORIES day over day, not just the current snapshot.
--
-- Public-read reference data (predictors / API read it), service_role writes (the cron),
-- so it follows the public-read Supabase grant pattern.

CREATE TABLE IF NOT EXISTS public.procedure_snapshots (
    id                      BIGSERIAL PRIMARY KEY,
    carriage_id             UUID NOT NULL REFERENCES public.legislative_carriages(id) ON DELETE CASCADE,
    snapshot_date           DATE NOT NULL,
    oeil_procedure_ref      TEXT,

    -- slow state (canonical, off the carriage row)
    current_status          TEXT,
    days_in_current_status  INTEGER NOT NULL DEFAULT 0,
    lead_committee          TEXT,
    rapporteur_mep_id       TEXT,
    text_type               TEXT,
    policy_areas            TEXT[] NOT NULL DEFAULT '{}',
    celex_numbers           TEXT[] NOT NULL DEFAULT '{}',
    num_opinion_committees  INTEGER NOT NULL DEFAULT 0,
    num_status_changes      INTEGER NOT NULL DEFAULT 0,

    -- fast-signal counts (the new value the predictors are blind to)
    num_amendments          INTEGER NOT NULL DEFAULT 0,
    num_documents           INTEGER NOT NULL DEFAULT 0,
    num_committee_work      INTEGER NOT NULL DEFAULT 0,
    num_lobby_meetings      INTEGER NOT NULL DEFAULT 0,
    num_eprs_briefings      INTEGER NOT NULL DEFAULT 0,

    -- reconciliation flags (honest): lobby/EPRS only resolvable with an OEIL ref
    ref_linked              BOOLEAN NOT NULL DEFAULT false,
    is_estimated            BOOLEAN NOT NULL DEFAULT false,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT procedure_snapshots_carriage_date_uq UNIQUE (carriage_id, snapshot_date)
);

-- trajectory queries read the last N days for one carriage, newest first
CREATE INDEX IF NOT EXISTS idx_procedure_snapshots_carriage_date
    ON public.procedure_snapshots (carriage_id, snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_procedure_snapshots_date
    ON public.procedure_snapshots (snapshot_date);

-- RLS: public read, service_role write
ALTER TABLE public.procedure_snapshots ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "procedure_snapshots_anon_read" ON public.procedure_snapshots;
CREATE POLICY "procedure_snapshots_anon_read"
    ON public.procedure_snapshots FOR SELECT TO anon USING (true);

DROP POLICY IF EXISTS "procedure_snapshots_authenticated_read" ON public.procedure_snapshots;
CREATE POLICY "procedure_snapshots_authenticated_read"
    ON public.procedure_snapshots FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "procedure_snapshots_service_all" ON public.procedure_snapshots;
CREATE POLICY "procedure_snapshots_service_all"
    ON public.procedure_snapshots FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Supabase Data API grants (mandatory; default grant removed 30 Oct 2026)
GRANT SELECT ON public.procedure_snapshots TO anon;
GRANT SELECT ON public.procedure_snapshots TO authenticated;
GRANT ALL ON public.procedure_snapshots TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.procedure_snapshots_id_seq TO service_role;
