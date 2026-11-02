-- 324: ft_funded_projects.first_seen, when Brubru first saw the project (2 Nov 2026, Victor's decision;
-- problem register O140).
--
-- The lists served `scraped_at` as `creation_date`, and both loaders stamp `scraped_at` on every read, so a
-- project's creation_date moved with each sync and 14,039 of 115,122 were served as created after their last
-- change (the run of 1 Nov 2026 05:08-05:32 UTC), against the standard's "when Brubru first saw the item,
-- never after its last change". From now on `first_seen` is that date and no writer touches it.
--
-- The true first sight of a row already re-read is gone. Rows are filled once, under
-- brubru.keep_change_signal (nothing in the project changed), with the earliest stamp held:
-- LEAST(scraped_at, last_updated). See scripts/fill_ft_funded_projects_first_seen.py.
ALTER TABLE public.ft_funded_projects ADD COLUMN IF NOT EXISTS first_seen TIMESTAMP;
ALTER TABLE public.ft_funded_projects ALTER COLUMN first_seen SET DEFAULT now();
COMMENT ON COLUMN public.ft_funded_projects.first_seen IS
    'When Brubru first saw the project (the items'' creation_date). scraped_at is the last read.';
