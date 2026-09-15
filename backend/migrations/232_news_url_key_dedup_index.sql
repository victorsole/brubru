-- 232_news_url_key_dedup_index.sql
-- One URL identity for the two news stores, and the index that makes it cheap.
--
-- WHY
-- ---
-- /api/v2/news/* unions economy_items (agencies) with eu_news_items (institutions) at
-- read time. The union had no way to recognise the same article in both stores, so it
-- relied on the two halves being disjoint BY BODY: only bodies with zero news rows in
-- economy_items were admitted from eu_news_items. Measured 11 Sep 2026, that rule
-- neither prevented duplicates nor allowed coverage:
--
--   * it served 274 duplicates anyway -- Commission-tagged eu_news_items rows whose URL
--     is also an economy_items news row of HaDEA (124), CINEA (58), REA (47), EACEA (24);
--   * it kept 2,077 official items out of the API entirely (EEAS 719, EEA 500, EESC 343,
--     ECB 89, EASA 78, ...) because their bodies also had SOME economy news rows.
--
-- The honest rule is per URL, not per body: serve an institutional row unless the same
-- URL is already served by the agency half. That needs a canonical URL key and an index.
-- A correlated lookup without one timed out (economy_items is ~570K rows and had no
-- index on public_url alone; the only one is UNIQUE (body_code, item_type, public_url)).
--
-- WHAT
-- ----
-- news_url_key(url): lower-case, whitespace trimmed, query string and fragment removed,
-- trailing slash removed, scheme and leading "www." removed. IMMUTABLE so it can back an
-- index, and SQL-language so the planner inlines it and matches the index expression.
-- ENISA stored "https://www.enisa.europa.eu/news/slug " (trailing space) beside the same
-- article without it; the Commission and an executive agency list one article under
-- "http://" and "https://www."; this key makes those one URL.
--
-- A PARTIAL index on the news rows only (~12K of ~570K), because the union only ever
-- compares against economy_items item_type IN ('news','press_release'). The query must
-- repeat that literal predicate for the planner to use the index.
--
-- PRODUCTION NOTE (same as 214): on prod the index is built CONCURRENTLY out-of-band so
-- the table is not locked:
--     CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_economy_items_news_url_key
--       ON public.economy_items (public.news_url_key(public_url))
--       WHERE item_type IN ('news', 'press_release');
-- The migration runner wraps SQL in a transaction, where CONCURRENTLY is not allowed, so
-- this file uses the plain form; on a fresh database both produce the same index, and
-- IF NOT EXISTS makes a replay after the out-of-band build a no-op.
--
-- No table, no RLS change: functions are EXECUTE-able by PUBLIC by default in Postgres,
-- and no grant is needed for an index.

CREATE OR REPLACE FUNCTION public.news_url_key(url text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
RETURNS NULL ON NULL INPUT
AS $$
  SELECT regexp_replace(
           rtrim(lower(split_part(split_part(btrim(url), '#', 1), '?', 1)), '/'),
           '^https?://(www\.)?', '')
$$;

COMMENT ON FUNCTION public.news_url_key(text) IS
  'Canonical URL identity for news dedup across economy_items and eu_news_items: '
  'lower, trimmed, no query/fragment, no trailing slash, no scheme or leading www. '
  'Backs ix_economy_items_news_url_key (migration 232).';

CREATE INDEX IF NOT EXISTS ix_economy_items_news_url_key
  ON public.economy_items (public.news_url_key(public_url))
  WHERE item_type IN ('news', 'press_release');
