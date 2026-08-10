-- 212: keep the coordinator's PIC on ft_funded_projects.
--
-- Context. `ingest_ft_projects_nonh2020.py` stored SEDIA's participants payload
-- with `str(participants[0])[:300]`, which dropped a JSON blob into a column
-- called coordinator_name and cut it 300 characters in. All 28,125 affected
-- rows were exactly 300 characters and none was parseable.
--
-- ft_participants was rebuilt by regex-scraping the PIC and legal name out of
-- the surviving head of those fragments. Repairing coordinator_name (which had
-- to happen: the Tenderator feed rendered an empty Organisation for every one
-- of them) removes that fragment, and with it the only place the PIC existed.
-- Without somewhere to put it, the weekly ft_participants refresh becomes a
-- no-op the first time it runs after the repair.
--
-- So the PIC gets its own column. It is the Participant Identification Code,
-- the F&T Portal's stable key for an organisation, and it is the join between
-- a funded project and the participant register.
--
-- No RLS or GRANT changes: this adds a column to an existing table, whose
-- policies and grants already cover it.

ALTER TABLE public.ft_funded_projects
    ADD COLUMN IF NOT EXISTS coordinator_pic VARCHAR(20);

COMMENT ON COLUMN public.ft_funded_projects.coordinator_pic IS
    'F&T Portal Participant Identification Code of the coordinating organisation. '
    'Joins to ft_participants.pic. Null for rows ingested before 10 Aug 2026, '
    'whose PIC was lost with the truncated participants blob.';

-- The register join, and the "who coordinated what" lookup behind the
-- Tenderator drawer's past-grantees panel.
CREATE INDEX IF NOT EXISTS ix_ft_projects_coordinator_pic
    ON public.ft_funded_projects (coordinator_pic)
    WHERE coordinator_pic IS NOT NULL;
