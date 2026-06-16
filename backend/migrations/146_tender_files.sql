-- 146_tender_files.sql
-- Tender Docs v1 (16 Jun 2026).
--
-- Container row that groups all the documents the user writes for ONE
-- EU funding application — e.g. a single EIC Accelerator submission has
-- a Part B narrative, a pitch deck, a video script, an FTO note, an
-- implementation plan, a financial plan, letters of intent etc. Each of
-- those is a row in `user_documents`; they all point back to ONE row
-- here via `user_documents.tender_file_id`.
--
-- Anchor metadata (programme / sub_instrument / topic_id / stage /
-- funding_mode / deadline / status / scaffold_version) lives here once,
-- not duplicated on every doc.

CREATE TABLE IF NOT EXISTS public.tender_files (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title               TEXT NOT NULL,

    -- Programme anchor
    programme           TEXT NOT NULL,                 -- 'EIC' | 'HE' | 'CEF' | 'LIFE' | 'EDF' | 'TED' | …
    sub_instrument      TEXT,                          -- 'accelerator' | 'pathfinder-open' | 'pathfinder-challenges' | 'transition' | 'step' | 'aic' | 'pre-accelerator' | 'prize' | …
    stage               TEXT,                          -- 'stage-1' | 'stage-2' | 'single-stage' | 'interview'
    topic_id            TEXT,                          -- F&T Portal topic id (e.g. HORIZON-EIC-2026-ACCELERATOR-01) — null if no specific topic yet
    topic_variant       TEXT,                          -- e.g. 'challenge-2.4' for Accelerator Challenges
    funding_mode        TEXT,                          -- 'grant-only' | 'equity-only' | 'blended' | null

    -- Process anchors
    deadline_iso        TIMESTAMPTZ,                   -- the call cut-off
    status              TEXT NOT NULL DEFAULT 'drafting',  -- 'drafting' | 'ready-to-submit' | 'submitted' | 'won' | 'lost' | 'seal-of-excellence'

    -- Template anchor
    template_id         TEXT NOT NULL,                 -- 'eic-accelerator-stage-1', 'eic-pathfinder-open', ...
    scaffold_version    TEXT NOT NULL,                 -- '2.0-22.10.2025'

    -- Optional cross-link to a saved/tracked tender row
    tender_track_id     UUID,                          -- nullable; no FK to keep the table independent of tender_tracks evolution

    -- Flex metadata
    extra               JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tender_files_user_id
    ON public.tender_files (user_id);
CREATE INDEX IF NOT EXISTS idx_tender_files_programme
    ON public.tender_files (programme);
CREATE INDEX IF NOT EXISTS idx_tender_files_topic_id
    ON public.tender_files (topic_id);
CREATE INDEX IF NOT EXISTS idx_tender_files_status
    ON public.tender_files (status);

-- Add the FK column on user_documents so each doc points back to its file.
-- Plain idempotent ALTER — Postgres can't conditionally add a FK constraint
-- in one statement, so we split into 'add column' (idempotent) + 'attach FK'
-- (best-effort if already attached).
ALTER TABLE public.user_documents
    ADD COLUMN IF NOT EXISTS tender_file_id UUID;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'user_documents'
          AND constraint_name = 'user_documents_tender_file_id_fkey'
    ) THEN
        ALTER TABLE public.user_documents
            ADD CONSTRAINT user_documents_tender_file_id_fkey
            FOREIGN KEY (tender_file_id)
            REFERENCES public.tender_files(id)
            ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_user_documents_tender_file_id
    ON public.user_documents (tender_file_id);

-- updated_at trigger (mirrors the rest of the schema)
CREATE OR REPLACE FUNCTION public.set_tender_files_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tender_files_set_updated_at ON public.tender_files;
CREATE TRIGGER tender_files_set_updated_at
    BEFORE UPDATE ON public.tender_files
    FOR EACH ROW
    EXECUTE FUNCTION public.set_tender_files_updated_at();

-- RLS: tender_files are PRIVATE to the user. authenticated users CRUD their
-- own rows, service_role has full access. Mirrors migrations 041/042/064/065/069
-- pattern for user-owned tables (set 15 May 2026, codified 30 Oct 2026).
ALTER TABLE public.tender_files ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tender_files_owner_select" ON public.tender_files;
CREATE POLICY "tender_files_owner_select"
    ON public.tender_files
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "tender_files_owner_insert" ON public.tender_files;
CREATE POLICY "tender_files_owner_insert"
    ON public.tender_files
    FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "tender_files_owner_update" ON public.tender_files;
CREATE POLICY "tender_files_owner_update"
    ON public.tender_files
    FOR UPDATE
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "tender_files_owner_delete" ON public.tender_files;
CREATE POLICY "tender_files_owner_delete"
    ON public.tender_files
    FOR DELETE
    TO authenticated
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "tender_files_service_all" ON public.tender_files;
CREATE POLICY "tender_files_service_all"
    ON public.tender_files
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Supabase Data API grants (mandatory on new public.* tables per CLAUDE.md).
GRANT SELECT, INSERT, UPDATE, DELETE ON public.tender_files TO authenticated;
GRANT ALL ON public.tender_files TO service_role;

COMMENT ON TABLE public.tender_files IS
    'Container row grouping all user_documents that make up ONE EU funding application (e.g. a single EIC Accelerator submission). Programme/sub_instrument/topic_id/funding_mode anchor metadata lives here.';
COMMENT ON COLUMN public.tender_files.template_id IS
    'JSON template stub: eic-accelerator-stage-1 / eic-pathfinder-open / ... Maps to backend/knowledge_base/funding_templates/<template_id>.json';
COMMENT ON COLUMN public.tender_files.scaffold_version IS
    'EU template version e.g. 2.0-22.10.2025 — frozen on creation; user can switch to a newer scaffold via UI later.';
