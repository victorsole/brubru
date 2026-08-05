-- 202_gi_refine_track.sql
-- Task 1.#3: persist the honest refinement-track partition of every GI, so the
-- supervised member-state workstream (1.2) and the comarca crosswalk (1.3) have a
-- durable, queryable worklist instead of a re-derived, mixed bucket.
--
-- Values (written by scripts/gi_geo_classify.py):
--   precise         -- already commune-level (name_lau / annex_lau); done.
--   region_exact    -- area genuinely IS a whole province/region/island; correctly coarse.
--   part_of         -- a partitive slice of a unit -> 1.2 (member-state geodata, supervised).
--   comarca         -- Spanish/Catalan comarca-defined -> 1.3 (Idescat-style crosswalk).
--   enumerable_todo -- stored text still carries a named commune list -> 1.1 residual.
--   no_text         -- geographical_area empty/near-empty; needs re-extraction first.
--   unknown         -- coarse, mapped, no decisive signal; flagged for manual review.
--
-- gi_details already has RLS + grants from its creation migration; this is a plain
-- nullable column addition, no new access-control surface.

ALTER TABLE public.gi_details ADD COLUMN IF NOT EXISTS geo_refine_track varchar(20);

COMMENT ON COLUMN public.gi_details.geo_refine_track IS
  'GI mapping refinement track (task 1.#3): precise | region_exact | part_of | comarca | enumerable_todo | no_text | unknown';

CREATE INDEX IF NOT EXISTS idx_gi_details_refine_track ON public.gi_details (geo_refine_track);
