-- 236: every rapporteur of a legislative file, not only the first (23 Sep 2026).
--
-- Why: legislative_carriages.rapporteur_name is one text column. A Rule 58 joint
-- file has one rapporteur per joint committee: the Industrial Accelerator Act has
-- three (INTA, ITRE, IMCO), the Cloud and AI Development Act two. The column
-- could only ever hold the first, so two of three co-rapporteurs were invisible
-- to everything that read the carriage.
--
-- rapporteur_name stays as it is for its existing readers. `rapporteurs` holds the
-- full list in OEIL's order: [{name, group, committee, appointed}], written by
-- scripts/backfill_oeil_committee_roles.py from the stored OEIL page.
-- Existing table: RLS and grants are unchanged.

ALTER TABLE public.legislative_carriages ADD COLUMN IF NOT EXISTS rapporteurs jsonb;

COMMENT ON COLUMN public.legislative_carriages.rapporteurs IS
  'Every rapporteur of the responsible committee(s), OEIL order: [{name, group, committee, appointed}]. Rule 58 joint files have one per committee.';
