-- Move 4 (15 Jun 2026): Tenderator pipeline CRM.
-- Lets a user track ANY opportunity (TED, F&T proposals/tenders/projects,
-- agency, intl_coop) through a configurable status pipeline. Replaces the
-- TAS-style Excel tracker.
--
-- Generic vs tender-specific: tender_matches.tender_id is a FK to tenders.id,
-- so it only supports TED rows. tender_pipeline uses a free-text
-- opportunity_id ("ted:123" / "ft_proposals:uuid" / "intl_coop:456") so
-- every Tenderator source can flow through the same pipeline.
--
-- The UI snapshots the opportunity's title/org/budget/deadline at add-time
-- so the row stays useful even if the upstream notice rolls off.

CREATE TABLE IF NOT EXISTS public.tender_pipeline (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,

    -- Opportunity reference (source-qualified id from the unified feed).
    opportunity_id TEXT NOT NULL,
    source VARCHAR(20) NOT NULL,   -- ted | ft_proposals | ft_tenders | ft_projects | agency | intl_coop

    -- Snapshot fields (cached at add-time so the card stays useful).
    title TEXT NOT NULL,
    organisation TEXT,
    country VARCHAR(120),
    programme TEXT,
    deadline TIMESTAMPTZ,
    budget NUMERIC,
    currency VARCHAR(8) DEFAULT 'EUR',
    source_url TEXT,

    -- Pipeline state.
    status VARCHAR(20) NOT NULL DEFAULT 'lead',
    -- Allowed: lead | drafting | submitted | awarded | executing | paid | lost | cancelled
    next_step TEXT,
    next_step_due DATE,
    pm_assignee TEXT,
    notes TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT tender_pipeline_status_check CHECK (status IN (
        'lead','drafting','submitted','awarded','executing','paid','lost','cancelled'
    )),
    CONSTRAINT tender_pipeline_user_opp_uk UNIQUE (user_id, opportunity_id)
);

CREATE INDEX IF NOT EXISTS idx_tender_pipeline_user_status
    ON public.tender_pipeline (user_id, status);
CREATE INDEX IF NOT EXISTS idx_tender_pipeline_user_deadline
    ON public.tender_pipeline (user_id, deadline);

-- updated_at autoset
CREATE OR REPLACE FUNCTION public.tender_pipeline_touch() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tender_pipeline_touch_trg ON public.tender_pipeline;
CREATE TRIGGER tender_pipeline_touch_trg
    BEFORE UPDATE ON public.tender_pipeline
    FOR EACH ROW EXECUTE FUNCTION public.tender_pipeline_touch();

-- RLS: each user sees + edits only their own rows.
ALTER TABLE public.tender_pipeline ENABLE ROW LEVEL SECURITY;

CREATE POLICY tender_pipeline_owner_select ON public.tender_pipeline
    FOR SELECT USING (auth.uid()::text = user_id::text);
CREATE POLICY tender_pipeline_owner_insert ON public.tender_pipeline
    FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);
CREATE POLICY tender_pipeline_owner_update ON public.tender_pipeline
    FOR UPDATE USING (auth.uid()::text = user_id::text);
CREATE POLICY tender_pipeline_owner_delete ON public.tender_pipeline
    FOR DELETE USING (auth.uid()::text = user_id::text);

-- Grants per memory rule: authenticated CRUD on user-owned table; service_role full.
GRANT SELECT, INSERT, UPDATE, DELETE ON public.tender_pipeline TO authenticated;
GRANT ALL ON public.tender_pipeline TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.tender_pipeline_id_seq TO authenticated;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE public.tender_pipeline_id_seq TO service_role;
