-- 252: /api/v2/news/all gains a third kind, `publication`, so the dedup index must cover it.
--
-- The institutional half of the union is served only when the agency half does not already
-- serve the same URL, and that NOT EXISTS is written with a LITERAL item_type list so the
-- planner can prove it matches this partial index. The list was ('news','press_release').
-- Adding 'publication' to the predicate without adding it here would leave the index unusable
-- for the new predicate and turn the dedup into a sequential scan of 564,719 rows on every
-- page of every news call.
--
-- Built CONCURRENTLY: economy_items is written by the agency syncs throughout the day and a
-- plain CREATE INDEX takes a lock that would block them.

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_economy_items_news_url_key_v2
    ON public.economy_items (public.news_url_key(public_url))
    WHERE item_type::text = ANY (ARRAY['news', 'press_release', 'publication']::text[]);

DROP INDEX CONCURRENTLY IF EXISTS public.ix_economy_items_news_url_key;
