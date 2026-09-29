-- 254: the kind a news item is served under is decided ONCE and then frozen.
--
-- GovClipping keys its search documents on the kind we serve (eu:press_release:<id>
-- vs eu:publication:<id>). When an item moved between kinds they got a second
-- document that nothing deleted, their write was refused as an identity collision,
-- and the feed's sync window stopped advancing. Jordi's ask, 29 Sep 2026: "lo
-- important es que no hi hagi reclassificacions en un futur".
--
-- The scraper-side cause (a guessed item_type overwriting a read one) was fixed in
-- 05948290, but that is application discipline across TEN writers of item_type, and
-- discipline across ten writers is what fails. The kind therefore gets a column of
-- its own with ONE owner -- this trigger -- so no writer can move it by accident.
--
-- Note the internal taxonomy is deliberately NOT frozen: eu_news_items.item_type has
-- 13 values feeding 3 kinds, so a correction from 'statement' to 'speech' still
-- happens and still never reaches a client, because both map to 'news'. Only the
-- published kind is pinned.
--
-- A DELIBERATE reclassification is still possible, but it has to say so:
--     SET LOCAL brubru.allow_kind_change = 'on';
-- inside the transaction. That is the difference between a decision and a side effect.

ALTER TABLE eu_news_items ADD COLUMN IF NOT EXISTS news_kind TEXT;
ALTER TABLE economy_items ADD COLUMN IF NOT EXISTS news_kind TEXT;

COMMENT ON COLUMN eu_news_items.news_kind IS
    'The kind this item is served under by /api/v2/news (news | press_release | '
    'publication), or NULL when the item is not in the news feed. Set once at insert '
    'and frozen by trg_eu_news_items_pin_kind; change it only under '
    'SET LOCAL brubru.allow_kind_change = ''on''.';
COMMENT ON COLUMN economy_items.news_kind IS
    'The kind this item is served under by /api/v2/news, or NULL when it is not a news '
    'item. Set once at insert and frozen by trg_economy_items_pin_kind.';


-- The two tables reach the same three kinds from different vocabularies, so the
-- mapping lives here, once, instead of in the CASE expressions the API repeated.
CREATE OR REPLACE FUNCTION brubru_news_kind_of(p_table text, p_item_type text)
RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN p_table = 'economy_items' THEN
            CASE WHEN p_item_type IN ('news', 'press_release', 'publication')
                 THEN p_item_type END
        ELSE
            CASE
                WHEN p_item_type = 'press' THEN 'press_release'
                WHEN p_item_type IN ('publication', 'report') THEN 'publication'
                WHEN p_item_type IN ('news', 'story', 'statement', 'speech') THEN 'news'
            END
    END
$$;


CREATE OR REPLACE FUNCTION brubru_pin_news_kind()
RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    allowed boolean := coalesce(
        current_setting('brubru.allow_kind_change', true), '') = 'on';
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.news_kind IS NULL THEN
            NEW.news_kind := brubru_news_kind_of(TG_TABLE_NAME, NEW.item_type);
        END IF;
        RETURN NEW;
    END IF;

    -- A kind already decided is the one we keep, whatever this write says. A row that
    -- has none yet (it was not a news item, or predates this column) may still take one.
    IF OLD.news_kind IS NOT NULL AND NOT allowed THEN
        NEW.news_kind := OLD.news_kind;
    ELSIF NEW.news_kind IS NULL OR NEW.news_kind IS NOT DISTINCT FROM OLD.news_kind THEN
        NEW.news_kind := coalesce(
            brubru_news_kind_of(TG_TABLE_NAME, NEW.item_type), OLD.news_kind);
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_eu_news_items_pin_kind ON eu_news_items;
CREATE TRIGGER trg_eu_news_items_pin_kind
    BEFORE INSERT OR UPDATE ON eu_news_items
    FOR EACH ROW EXECUTE FUNCTION brubru_pin_news_kind();

DROP TRIGGER IF EXISTS trg_economy_items_pin_kind ON economy_items;
CREATE TRIGGER trg_economy_items_pin_kind
    BEFORE INSERT OR UPDATE ON economy_items
    FOR EACH ROW EXECUTE FUNCTION brubru_pin_news_kind();


-- Backfill what each row is being served as TODAY, so no client sees a single item
-- move on the day this ships.
UPDATE eu_news_items SET news_kind = brubru_news_kind_of('eu_news_items', item_type)
 WHERE news_kind IS NULL
   AND item_type IN ('news', 'press', 'story', 'statement', 'speech', 'publication', 'report');

UPDATE economy_items SET news_kind = item_type
 WHERE news_kind IS NULL
   AND item_type IN ('news', 'press_release', 'publication');

CREATE INDEX IF NOT EXISTS ix_eu_news_items_news_kind
    ON eu_news_items (news_kind) WHERE news_kind IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_economy_items_news_kind
    ON economy_items (news_kind) WHERE news_kind IS NOT NULL;
