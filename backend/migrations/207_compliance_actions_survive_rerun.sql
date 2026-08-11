-- 207: make a finding's remediation state survive a re-run of the analysis.
--
-- compliance_actions was keyed on gap_finding_id alone. gap_findings are
-- recreated from scratch on every analysis run, so triage stayed bound to the
-- run it was entered against: it survived a page reload but vanished the
-- moment the user re-ran the analysis against an updated document. Re-running
-- is the whole point of a compliance workspace, so that made the feature
-- shipped on 8 Aug 2026 half of one.
--
-- The durable identity of "this obligation, for this user, in this package" is
-- (user_id, cluster_id, requirement_id). gap_finding_id stays, but demoted to
-- a pointer at the most recent finding the action was touched from -- useful
-- for tracing, never for identity.
--
-- No new GRANTs: ALTER TABLE on an existing table that already carries its
-- RLS policies and role grants.

ALTER TABLE public.compliance_actions
    ADD COLUMN IF NOT EXISTS requirement_id INTEGER
        REFERENCES public.law_requirements(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS cluster_id INTEGER
        REFERENCES public.law_clusters(id) ON DELETE CASCADE;

-- Backfill from the finding each existing action was entered against.
UPDATE public.compliance_actions a
   SET requirement_id = f.requirement_id,
       cluster_id     = an.cluster_id
  FROM public.gap_findings f
  JOIN public.compliance_analyses an ON an.id = f.analysis_id
 WHERE f.id = a.gap_finding_id
   AND (a.requirement_id IS NULL OR a.cluster_id IS NULL);

-- One action per obligation per user per package. This is what lets a re-run
-- find the state that was entered against a previous run.
CREATE UNIQUE INDEX IF NOT EXISTS uniq_compliance_action_user_cluster_req
    ON public.compliance_actions (user_id, cluster_id, requirement_id)
 WHERE requirement_id IS NOT NULL AND cluster_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_compliance_actions_requirement
    ON public.compliance_actions (requirement_id);

-- NB: keep semicolons out of COMMENT literals. Simple migration runners split
-- statements on ';' and a semicolon inside a string truncates the statement.
COMMENT ON COLUMN public.compliance_actions.requirement_id IS
  'Durable identity of the obligation being remediated. Key triage state on (user_id, cluster_id, requirement_id), never on gap_finding_id, which is recreated on every analysis run.';
