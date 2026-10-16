-- 296: a fetch stamp is not a change. economy_items and eu_news_items stop counting it.
--
-- Migration 271 gave both news stores an updated_at kept by brubru_touch_if_changed, which
-- moves updated_at whenever any column other than the ignored ones differs. It ignored
-- none, and every writer stamps a fetch time on each run:
--   economy_items:  the sync_economy upsert sets fetched_at = now() on every conflict;
--   eu_news_items:  services/news/fetch_anchor.stamp_fetched sets fetched_at = now() on
--                   every row a sync sights. Its scraped_at (set on insert) is a stamp
--                   too and is ignored with it, so a writer that refreshes it later
--                   cannot reopen the defect.
-- So updated_at recorded the last fetch, not the last change. Measured 16 Oct 2026:
-- updated_at = fetched_at on 603,018 of 603,054 non-news economy rows and 20,882 of
-- 20,963 news rows, and 10,967 of those news rows read as "changed" within two days.
-- /api/v2/news/all filters updated_from on this column, so an incremental sync re-pulled
-- rows that had not changed. Found by the API audit (step 2, Cedefop tenders).
--
-- Every other table on this trigger already ignores its stamps (scraped_at, fetched_at,
-- body_fetched_at, last_synced_at ...); these two were the exceptions.
--
-- Existing values stay: they are the last fetch, which is never earlier than the last
-- real change, so a client re-reads a row it may hold rather than missing one that moved.
-- From now on a re-fetch that finds the same content leaves updated_at alone.

DROP TRIGGER IF EXISTS trg_economy_items_touch_if_changed ON economy_items;
CREATE TRIGGER trg_economy_items_touch_if_changed
    BEFORE UPDATE ON economy_items
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', 'fetched_at', 'creation_date');

DROP TRIGGER IF EXISTS trg_eu_news_items_touch_if_changed ON eu_news_items;
CREATE TRIGGER trg_eu_news_items_touch_if_changed
    BEFORE UPDATE ON eu_news_items
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', 'scraped_at,fetched_at', 'created_at');
