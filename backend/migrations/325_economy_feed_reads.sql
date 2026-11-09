-- 325_economy_feed_reads.sql (O237, 9 Nov 2026)
--
-- When scripts/sync_economy.py last READ each agency feed, one row per (body_code, item_type).
--
-- Until now the sync stamped fetched_at = now() on every item of every feed on every run, so
-- max(fetched_at) per feed meant "the cron read this feed". That stamp rewrote every row each
-- run (14 indexes, the touch and tsvector triggers over the full text): about half of the
-- database's write log over the weekend of 7-8 Nov. The upsert now skips items that did not
-- change, so their fetched_at stays put, and the read is recorded here instead.
--
-- Readers take the later of this and max(fetched_at), so a feed with no row here yet reads as
-- before: GET /api/v2/news/latest (`last_fetched`, `fetch_age_days`) and
-- scripts/scraper_health.py. One writer: sync_economy._record_feed_reads, and only for feeds
-- that returned items (a run that read nothing must go stale).
--
-- Column trio as elsewhere: scraped_at is the last read (the anchor), first_seen the first,
-- last_updated the last write of this row.

CREATE TABLE IF NOT EXISTS public.economy_feed_reads (
    body_code     text        NOT NULL,
    item_type     text        NOT NULL,
    items_read    integer     NOT NULL,
    scraped_at    timestamptz NOT NULL DEFAULT now(),
    first_seen    timestamptz NOT NULL DEFAULT now(),
    last_updated  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (body_code, item_type)
);

COMMENT ON TABLE public.economy_feed_reads IS
    'When sync_economy.py last read each agency feed (O237). Readers take greatest(max(economy_items.fetched_at), scraped_at).';

ALTER TABLE public.economy_feed_reads ENABLE ROW LEVEL SECURITY;

-- Public read, like scraper_health_state (fleet freshness is not private); only service_role writes.
DROP POLICY IF EXISTS economy_feed_reads_read ON public.economy_feed_reads;
CREATE POLICY economy_feed_reads_read ON public.economy_feed_reads
    FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS economy_feed_reads_service_all ON public.economy_feed_reads;
CREATE POLICY economy_feed_reads_service_all ON public.economy_feed_reads
    FOR ALL TO service_role USING (true) WITH CHECK (true);

GRANT SELECT ON public.economy_feed_reads TO anon, authenticated;
GRANT ALL    ON public.economy_feed_reads TO service_role;
