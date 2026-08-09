-- 205: give law_clusters an explicit startup-focus flag.
--
-- Why: GET /api/eu-law-comply/clusters?startup_focused=true filtered on
-- `LawCluster.id > 11`, hardcoded when clusters 12-21 happened to be the ten
-- startup packages. Every cluster seeded since (the canon, pharma, state-aid
-- and textile clusters, ids 22 to 62) fell on the wrong side of that
-- comparison, so the endpoint returned 51 clusters as "startup packages"
-- instead of 10. An ID range is not a classification.
--
-- Backfill is by name because that is exactly what distinguishes the ten:
-- every one is named "<sector> Startup ...". Verified before writing:
--   SELECT id, name FROM law_clusters WHERE name ILIKE '%startup%';  -- 12..21
--
-- No new GRANTs needed: this is ALTER TABLE on an existing table, and
-- law_clusters already carries its RLS policies and role grants.

ALTER TABLE public.law_clusters
    ADD COLUMN IF NOT EXISTS is_startup_focused BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE public.law_clusters
   SET is_startup_focused = TRUE
 WHERE name ILIKE '%startup%';

CREATE INDEX IF NOT EXISTS idx_law_clusters_startup
    ON public.law_clusters (is_startup_focused)
 WHERE is_startup_focused;

-- NB: keep semicolons out of this literal. Simple migration runners split on
-- ';' and a semicolon inside a string silently truncates the statement.
COMMENT ON COLUMN public.law_clusters.is_startup_focused IS
  'True for the startup-oriented compliance packages. Set explicitly on new clusters, never inferred from the id, which is what broke the filter before.';
