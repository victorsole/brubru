-- 224: durable ledger for destructive answer post-processing
--
-- WHY (audit P5, 27 Aug 2026). `_strip_contradicting_act_numbers` DELETES text
-- from an answer the user is about to read. Until today it only emitted a
-- logger.warning, so when the Cyber Resilience Act defect surfaced we could not
-- answer the first question anyone asks: how many TRUE act numbers has this
-- transform removed, and from which answers? A destructive transform must
-- count what it destroys. Silence is not success.
--
-- Deliberately narrow: one row per deletion, no answer text (the answer is
-- already in chat_messages), no user identifiers.

CREATE TABLE IF NOT EXISTS public.post_processing_deletions (
    id                BIGSERIAL PRIMARY KEY,
    transform         TEXT        NOT NULL,
    act_name          TEXT        NOT NULL,
    asserted_number   TEXT,
    canonical_number  TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ppd_created_at ON public.post_processing_deletions (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ppd_act_name   ON public.post_processing_deletions (act_name);

ALTER TABLE public.post_processing_deletions ENABLE ROW LEVEL SECURITY;

-- Internal diagnostics only: no anon/authenticated read. The service role
-- writes it and /users + /audit-queries read it server-side.
DROP POLICY IF EXISTS ppd_service_all ON public.post_processing_deletions;
CREATE POLICY ppd_service_all ON public.post_processing_deletions
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Explicit grants are mandatory on new public.* tables: the default grant was
-- removed 30 Oct 2026, so a replay (staging spin-up, restore, new env) breaks
-- without these. See memory/feedback_supabase_data_api_grants.md.
GRANT ALL ON public.post_processing_deletions TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.post_processing_deletions_id_seq TO service_role;
