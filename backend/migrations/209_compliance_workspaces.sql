-- 209: give EU Law Comply a durable workspace, and make uploads survive a run.
--
-- Until now the unit of work was a disposable analysis. Documents were written
-- to /tmp, read once and deleted; `document_ids` was declared ARRAY(Integer)
-- against user_documents.id, which is a UUID, so it could never have been
-- populated at all and every analysis carried NULL. Nothing accumulated, so
-- there was no reason to come back.
--
-- compliance_workspaces is the durable object: one per (user, cluster). The
-- pairing already existed implicitly -- compliance_actions was re-keyed onto
-- (user_id, cluster_id, requirement_id) in migration 207 -- this gives it a row
-- so it can be named, listed and diffed.

CREATE TABLE IF NOT EXISTS public.compliance_workspaces (
    id           SERIAL PRIMARY KEY,
    user_id      UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    cluster_id   INTEGER NOT NULL REFERENCES public.law_clusters(id) ON DELETE CASCADE,
    name         VARCHAR(200),
    created_at   TIMESTAMP NOT NULL DEFAULT now(),
    updated_at   TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT uniq_workspace_user_cluster UNIQUE (user_id, cluster_id)
);

CREATE INDEX IF NOT EXISTS idx_compliance_workspaces_user
    ON public.compliance_workspaces (user_id);

-- Runs belong to a workspace. Nullable so existing rows stay valid.
ALTER TABLE public.compliance_analyses
    ADD COLUMN IF NOT EXISTS workspace_id INTEGER
        REFERENCES public.compliance_workspaces(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_compliance_analyses_workspace
    ON public.compliance_analyses (workspace_id);

-- The uploads a run was actually performed against. UUID[], because
-- user_documents.id is a UUID -- the existing document_ids INTEGER[] column is
-- left in place but is dead and always NULL.
ALTER TABLE public.compliance_analyses
    ADD COLUMN IF NOT EXISTS document_uuids UUID[];

-- Backfill: one workspace per (user, cluster) that already ran an analysis,
-- then attach the runs to it.
INSERT INTO public.compliance_workspaces (user_id, cluster_id, name, created_at)
SELECT a.user_id, a.cluster_id,
       (SELECT c.name FROM public.law_clusters c WHERE c.id = a.cluster_id),
       min(a.created_at)
  FROM public.compliance_analyses a
 GROUP BY a.user_id, a.cluster_id
ON CONFLICT (user_id, cluster_id) DO NOTHING;

UPDATE public.compliance_analyses a
   SET workspace_id = w.id
  FROM public.compliance_workspaces w
 WHERE w.user_id = a.user_id AND w.cluster_id = a.cluster_id
   AND a.workspace_id IS NULL;

-- Supabase Data API grants: mandatory on every new public table.
ALTER TABLE public.compliance_workspaces ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS compliance_workspaces_owner ON public.compliance_workspaces;
CREATE POLICY compliance_workspaces_owner ON public.compliance_workspaces
    FOR ALL TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

GRANT SELECT, INSERT, UPDATE, DELETE ON public.compliance_workspaces TO authenticated;
GRANT ALL ON public.compliance_workspaces TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.compliance_workspaces_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.compliance_workspaces_id_seq TO service_role;
