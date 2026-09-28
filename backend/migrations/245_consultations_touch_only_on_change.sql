-- 245: a change signal must move only when content changed, and one owner must decide.
--
-- /api/v1/consultations answers ?updated_from= off public_consultations.last_updated, and
-- the table's BEFORE UPDATE trigger set that column (and updated_at) to now() on every
-- update. The nightly sync upserts all 4,835 rows, so an incremental caller asking "what
-- changed since yesterday" was handed 85% of the corpus every night -- precisely what
-- incremental sync exists to avoid. Guarding the upsert's ON CONFLICT clause could not fix
-- it: the trigger runs after that clause and overwrites whatever it decided, which is why
-- the first attempt read as "the fix did not take".
--
-- So the decision moves into the trigger, the one place every write passes through, and the
-- function is written once here and reused by migrations 246-249 for every other table
-- behind a ?updated_from= filter. Same shape as brubru_track_content_change (migration 234).

-- Arguments (comma-separated lists, empty string for none):
--   TG_ARGV[0]  signal columns  set to now() when content changed, held otherwise
--   TG_ARGV[1]  ignored columns excluded from the comparison, left as the UPDATE wrote
--               them (an ingestion anchor such as scraped_at, which must move every run
--               because it answers "is this feed alive")
--   TG_ARGV[2]  creation anchors pinned to their OLD value, so no upsert can move them
--
-- Same shape as brubru_track_content_change (migration 234), generalised so every table
-- behind a ?updated_from= filter can adopt it.

CREATE OR REPLACE FUNCTION brubru_touch_if_changed()
RETURNS TRIGGER AS $$
DECLARE
    signal_cols text[] := string_to_array(TG_ARGV[0], ',');
    ignore_cols text[] := CASE WHEN TG_NARGS > 1 AND TG_ARGV[1] <> ''
                               THEN string_to_array(TG_ARGV[1], ',') ELSE '{}'::text[] END;
    anchor_cols text[] := CASE WHEN TG_NARGS > 2 AND TG_ARGV[2] <> ''
                               THEN string_to_array(TG_ARGV[2], ',') ELSE '{}'::text[] END;
    -- Generated columns are NOT computed yet in a BEFORE trigger, so NEW always holds
    -- NULL where OLD holds the stored value. Comparing them would report every row as
    -- changed (eu_laws.search_vector did exactly that, 28 Sep). Derived from the table
    -- rather than listed, so a column added later cannot silently re-break the guard.
    gen_cols text[] := (SELECT coalesce(array_agg(attname), '{}')
                        FROM pg_attribute
                        WHERE attrelid = TG_RELID AND attnum > 0
                          AND NOT attisdropped AND attgenerated <> '');
    all_ignored text[] := signal_cols || ignore_cols || anchor_cols || gen_cols;
    patch       jsonb;
BEGIN
    IF TG_OP = 'INSERT' THEN
        RETURN NEW;
    END IF;

    IF array_length(anchor_cols, 1) IS NOT NULL THEN
        NEW := jsonb_populate_record(NEW, (
            SELECT jsonb_object_agg(c, to_jsonb(OLD) -> c) FROM unnest(anchor_cols) c));
    END IF;

    IF (to_jsonb(NEW) - all_ignored) IS DISTINCT FROM (to_jsonb(OLD) - all_ignored) THEN
        patch := (SELECT jsonb_object_agg(c, to_jsonb(now()::timestamp)) FROM unnest(signal_cols) c);
    ELSE
        patch := (SELECT jsonb_object_agg(c, to_jsonb(OLD) -> c) FROM unnest(signal_cols) c);
    END IF;

    NEW := jsonb_populate_record(NEW, patch);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- public_consultations: /commission/consultations filters ?updated_from= on last_updated.
-- Both timestamp columns move together; scraped_at is the ingestion anchor and keeps
-- moving every run, which is what answers "is this feed still alive".
DROP TRIGGER IF EXISTS trigger_update_consultation_timestamp ON public_consultations;
DROP FUNCTION IF EXISTS update_consultation_updated_at();
CREATE TRIGGER trigger_update_consultation_timestamp
    BEFORE UPDATE ON public_consultations
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed(
        'updated_at,last_updated', 'scraped_at', 'created_at,first_seen');
