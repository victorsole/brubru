-- 271: give the two news stores a change signal.
--
-- GovClipping's news sync passes updated_from / updated_to. /api/v2/news/all accepted
-- neither, and FastAPI drops an undeclared query param silently with HTTP 200, so a
-- window in the year 2030 returned all 25,087 rows. They were re-pulling the entire
-- corpus every run believing it was a delta. The route's own comments already called
-- an earlier instance of this "the THIRD instance of the silent-drop bug on this one
-- endpoint" (`days` until 28 July 2026, `since`/`until` until 8 September 2026).
--
-- Declaring the parameter was not enough: neither table had anything to filter ON.
-- economy_items keeps creation_date and fetched_at, eu_news_items keeps scraped_at,
-- created_at and fetched_at. All of those say when WE touched the row, never when the
-- document changed.
--
-- updated_at is added nullable, which is metadata-only on a 3.5 GB table, and the
-- shared brubru_touch_if_changed trigger maintains it from here: it compares the row
-- and leaves updated_at alone when nothing actually changed, so a re-scrape that finds
-- an identical article does not read as a change.
--
-- The existing rows are seeded separately and in batches (seed_news_updated_at.py),
-- never in this migration: a single UPDATE over 601,949 rows rewrites the table.
ALTER TABLE economy_items  ADD COLUMN IF NOT EXISTS updated_at timestamptz;
ALTER TABLE eu_news_items  ADD COLUMN IF NOT EXISTS updated_at timestamptz;

COMMENT ON COLUMN economy_items.updated_at IS
    'When this row last actually changed (maintained by brubru_touch_if_changed). Seeded from fetched_at/creation_date as the first known bound; a fetch time is never served as a change signal thereafter.';
COMMENT ON COLUMN eu_news_items.updated_at IS
    'When this row last actually changed (maintained by brubru_touch_if_changed). Seeded from fetched_at/created_at as the first known bound.';

DROP TRIGGER IF EXISTS trg_economy_items_touch_if_changed ON economy_items;
CREATE TRIGGER trg_economy_items_touch_if_changed
    BEFORE UPDATE ON economy_items
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', '', 'creation_date');

DROP TRIGGER IF EXISTS trg_eu_news_items_touch_if_changed ON eu_news_items;
CREATE TRIGGER trg_eu_news_items_touch_if_changed
    BEFORE UPDATE ON eu_news_items
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', '', 'created_at');

-- The sync orders and slices on this column, and LIMIT/OFFSET over a non-unique sort
-- key serves some rows twice and skips others, so the index ends on the primary key.
CREATE INDEX IF NOT EXISTS idx_economy_items_updated_at ON economy_items (updated_at, id);
CREATE INDEX IF NOT EXISTS idx_eu_news_items_updated_at ON eu_news_items (updated_at, id);
