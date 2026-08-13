-- 214_economy_items_trgm_search.sql
-- Full-text (substring) index for the news/items corpus.
--
-- economy_items is ~440K rows (every EU body's news, press releases, events,
-- publications) and had NO index supporting text search — so every `ILIKE '%x%'`
-- (the `q=` param on /api/v2/news/all, per-body news search, the PPWR endpoint's
-- related-news, etc.) did a sequential scan over all 440K rows including full
-- article bodies (~0.5 s warm, ~3 s cold). eu_laws has a tsvector search index;
-- this table never got one.
--
-- Fix: pg_trgm GIN indexes on `title` and `summary`. pg_trgm is the correct
-- index type for the `ILIKE '%substring%'` the code already uses (a tsvector
-- would require rewriting every query to `@@ plainto_tsquery`). Verified: the
-- planner switches to a Bitmap Index Scan and the query drops from ~520 ms to
-- ~3 ms (EXPLAIN ANALYZE). body_txt is intentionally NOT trgm-indexed — a
-- trigram index over 440K full article bodies would be enormous and slow to
-- build; title+summary carry the topic-level relevance.
--
-- NOTE: on prod (440K rows) these indexes were built CONCURRENTLY out-of-band
-- (no table lock; ~25 s each) BEFORE this migration ran, so the IF NOT EXISTS
-- below is a no-op there. This file exists so fresh/rebuilt environments get the
-- same indexes. The migration runner wraps SQL in a transaction, so it must use
-- plain CREATE INDEX (CONCURRENTLY cannot run inside a transaction); on a fresh
-- (small) economy_items the brief build lock is harmless.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_economy_items_title_trgm
    ON public.economy_items USING gin (title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_economy_items_summary_trgm
    ON public.economy_items USING gin (summary gin_trgm_ops);
