-- 320: an index for the accent-insensitive text search on TED notices (30 Oct 2026, Victor's go).
--
-- `q` on /funding/tenders and /funding/opportunities (api/v1/_search.text_match) matches
-- unaccent(lower(column)) LIKE '%term%' (a regular expression with \y word bounds for a short term) on
-- the notice's title, description, summary and buyer name. With no index it read all 68,413 notices:
-- 3.7 s for one count (EXPLAIN ANALYZE, 30 Oct 2026), 8.6-14.2 s a page live.
--
-- unaccent() is STABLE (it reads its dictionary by search path), so it cannot be indexed. brubru_fold()
-- names the dictionary and is IMMUTABLE; text_match folds through it, so the query's expression is the
-- index's. The result is the same text as unaccent(lower(x)). pg_trgm GIN indexes serve both LIKE and
-- the regular expression. All four columns are indexed: one column without an index in the OR and the
-- planner reads the whole table again.
--
-- Run each statement on its own, outside a transaction: CREATE INDEX CONCURRENTLY does not lock writes.
CREATE OR REPLACE FUNCTION public.brubru_fold(text) RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
    AS $$ SELECT public.unaccent('public.unaccent'::regdictionary, lower($1)) $$;

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_tenders_title_fold_trgm ON public.tenders USING gin (public.brubru_fold(title) gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_tenders_description_fold_trgm ON public.tenders USING gin (public.brubru_fold(description) gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_tenders_summary_fold_trgm ON public.tenders USING gin (public.brubru_fold(summary) gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_tenders_official_name_fold_trgm ON public.tenders USING gin (public.brubru_fold(official_name::text) gin_trgm_ops);
