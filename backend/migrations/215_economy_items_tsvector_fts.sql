-- 215_economy_items_tsvector_fts.sql
-- Proper full-text search for the news/items corpus (title + summary + body).
--
-- Follows 214 (pg_trgm on title/summary). 214 made substring ILIKE on
-- title/summary fast, but the `q=` endpoints (/api/v2/news/all, per-body economy
-- news, events, consultations, funding, interoperable) also ILIKE `body_txt`,
-- which no trigram index can accelerate over 440K full article bodies (~1.3 s).
--
-- Fix: a tsvector `search_vector` over title+summary+body with a GIN index — the
-- same mechanism eu_laws already uses. The `q=` endpoints switch from
-- `... ILIKE '%q%'` to `search_vector @@ plainto_tsquery('english', :q)`: fast
-- body-inclusive word search (verified: 1.3 s -> a few ms).
--
-- Maintained by a TRIGGER (not a GENERATED column): economy_items is written by
-- ~10 raw-SQL ingest/backfill scripts with explicit column lists, and a trigger
-- keeps search_vector correct on every INSERT/UPDATE without a full-table rewrite
-- and without the generated-column ORM-insert hazard.
--
-- NOTE: on prod (440K rows) the column + trigger + a BATCHED backfill + a
-- CONCURRENT index were applied out-of-band (no long lock) BEFORE this migration
-- ran, so the statements below are no-ops there. This file gives fresh/rebuilt
-- environments the same result. The runner wraps SQL in a transaction, so this
-- uses a single backfill UPDATE + plain CREATE INDEX (fine on a small/fresh
-- economy_items; on a large table apply out-of-band as above).

ALTER TABLE public.economy_items ADD COLUMN IF NOT EXISTS search_vector tsvector;

CREATE OR REPLACE FUNCTION public.economy_items_tsv_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('english',
        coalesce(NEW.title, '') || ' ' || coalesce(NEW.summary, '') || ' ' || coalesce(NEW.body_txt, ''));
    RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS economy_items_tsv_trg ON public.economy_items;
CREATE TRIGGER economy_items_tsv_trg
    BEFORE INSERT OR UPDATE OF title, summary, body_txt
    ON public.economy_items
    FOR EACH ROW EXECUTE FUNCTION public.economy_items_tsv_update();

-- Backfill existing rows (fresh envs: one statement; prod: done batched out-of-band).
UPDATE public.economy_items
   SET search_vector = to_tsvector('english',
        coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(body_txt, ''))
 WHERE search_vector IS NULL;

CREATE INDEX IF NOT EXISTS idx_economy_items_search_vector
    ON public.economy_items USING gin (search_vector);
