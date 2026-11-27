-- 326_eu_news_items_news_url_key_index.sql
-- The index the BEFORE INSERT trigger on economy_items has always needed (O245, 27 Nov 2026).
--
-- brubru_carry_news_kind() runs before EVERY row an INSERT sends to economy_items, including
-- the rows ON CONFLICT then skips, and looks the item's address up in eu_news_items:
--
--     WHERE n.news_kind IS NOT NULL
--       AND news_url_key(n.source_url) = news_url_key(NEW.public_url) AND ...
--
-- economy_items has an index on news_url_key(public_url) (migrations 232, 252, 255).
-- eu_news_items never had one on news_url_key(source_url), so each lookup read all 22,086 news
-- rows and ran two regular expressions on every one: 282,749 whole-table scans and 5.98 billion
-- rows read in the two weeks to 27 Nov 2026, for a feed job that adds about 160 items a day.
-- Measured on production in a rolled-back transaction: 60 stored items sent back unchanged
-- touched 207,382 pages before the index and 779 after.
--
-- Applied to production on 27 Nov 2026 with CREATE INDEX CONCURRENTLY (1.7 s, 2.6 MB) followed
-- by ANALYZE eu_news_items, so the statement below is a no-op there. The runner wraps a
-- migration in a transaction, where CONCURRENTLY cannot run; the table is small enough for a
-- plain CREATE INDEX on a fresh or rebuilt environment.

CREATE INDEX IF NOT EXISTS ix_eu_news_items_news_url_key
    ON public.eu_news_items (public.news_url_key(source_url))
    WHERE news_kind IS NOT NULL;

ANALYZE public.eu_news_items;
