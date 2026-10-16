-- 297: two more tables stop re-stamping on a re-fetch, and the trigger says what changed.
--
-- Measured 16 Oct 2026 by sending GovClipping's 33 requests twice, 14 hours apart, and
-- comparing the rows field by field (scratchpad gc3/diff_prev.py):
--
--   ep_roll_call_votes  771 of 883 votes re-served with updated_at moved and no served
--                       field changed. Its trigger (trg_ep_rcv_votes_touch) sets
--                       updated_at = NOW() on EVERY update: it compares nothing.
--   eu_laws             the 6-hourly EuroVoc job re-stamped ~900 laws per run (1,800 of
--                       2,699 in one morning window had eurovoc_fetched_at moved, 897
--                       body_fetched_at); 132 of 356 compared had changed in no served
--                       field. The ignore list held only the derived CELEX parts.
--   consultations 139/156, commission_documents 646/814, plenary_tabled_texts 649/790,
--   tris_notifications 1,301/1,376, texts_adopted 46/146, parliamentary_questions 623:
--                       these already compare, with scraped_at ignored, and STILL
--                       re-stamp. Some column a client never sees moves on every run.
--                       Rather than guess it per table, the trigger now records WHICH
--                       columns differed each time it decides "changed", so the next
--                       migration sets each table's ignore list from one night of
--                       evidence. Names only, never values; rows older than 7 days are
--                       pruned by the trigger itself, so the table cannot grow unbounded.
--
-- Existing updated_at values stay: a client re-reads a row it may hold rather than
-- missing one that moved. From now on a re-fetch that finds the same content leaves the
-- signal alone on these two tables as well.

-- 1. The log. One row per touch that moved a signal: table, row id, the columns that
--    differed. No values. Read with:
--      SELECT table_name, unnest(changed_cols) col, count(*) FROM brubru_change_log
--      WHERE touched_at > now() - interval '1 day' GROUP BY 1,2 ORDER BY 1,3 DESC;
CREATE TABLE IF NOT EXISTS brubru_change_log (
    touched_at   timestamptz NOT NULL DEFAULT now(),
    table_name   text        NOT NULL,
    row_id       text,
    changed_cols text[]      NOT NULL
);
CREATE INDEX IF NOT EXISTS brubru_change_log_touched_at_idx ON brubru_change_log (touched_at);
ALTER TABLE brubru_change_log ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON brubru_change_log FROM anon, authenticated;
GRANT ALL ON brubru_change_log TO service_role;

-- 2. The function, unchanged in its decision; it now also writes the log line.
CREATE OR REPLACE FUNCTION public.brubru_touch_if_changed()
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
    old_j       jsonb;
    new_j       jsonb;
    diff_cols   text[];
    patch       jsonb;
BEGIN
    IF TG_OP = 'INSERT' THEN
        RETURN NEW;
    END IF;

    IF array_length(anchor_cols, 1) IS NOT NULL THEN
        NEW := jsonb_populate_record(NEW, (
            SELECT jsonb_object_agg(c, to_jsonb(OLD) -> c) FROM unnest(anchor_cols) c));
    END IF;

    -- A backfill that adds facts a row always had, not a change of the record, runs with
    -- SET LOCAL brubru.keep_change_signal = 'on': the signal columns keep OLD's value (293).
    -- Nothing else sets it, so every other writer still moves the signal.
    IF current_setting('brubru.keep_change_signal', true) = 'on' THEN
        NEW := jsonb_populate_record(NEW, (
            SELECT jsonb_object_agg(c, to_jsonb(OLD) -> c) FROM unnest(signal_cols) c));
        RETURN NEW;
    END IF;

    old_j := to_jsonb(OLD) - all_ignored;
    new_j := to_jsonb(NEW) - all_ignored;
    IF new_j IS DISTINCT FROM old_j THEN
        patch := (SELECT jsonb_object_agg(c, to_jsonb(now()::timestamp)) FROM unnest(signal_cols) c);
        -- The columns that differed, by name. This is what migration 298 reads.
        diff_cols := (SELECT coalesce(array_agg(k ORDER BY k), '{}')
                      FROM (SELECT key AS k FROM jsonb_each(new_j)
                            UNION SELECT key FROM jsonb_each(old_j)) keys
                      WHERE (new_j -> k) IS DISTINCT FROM (old_j -> k));
        INSERT INTO brubru_change_log (table_name, row_id, changed_cols)
        VALUES (TG_TABLE_NAME, (to_jsonb(NEW) ->> 'id'), diff_cols);
        -- Prune in passing, at most once per ~1,000 touches, so the log stays small.
        IF random() < 0.001 THEN
            DELETE FROM brubru_change_log WHERE touched_at < now() - interval '7 days';
        END IF;
    ELSE
        -- Keep OLD's signal, unless OLD has none: then the caller's value seeds it (272).
        patch := (SELECT jsonb_object_agg(c, coalesce(nullif(to_jsonb(OLD) -> c, 'null'::jsonb),
                                                      to_jsonb(NEW) -> c))
                  FROM unnest(signal_cols) c);
    END IF;

    NEW := jsonb_populate_record(NEW, patch);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. Votes: the comparing trigger replaces the one that stamped every update.
DROP TRIGGER IF EXISTS ep_rcv_votes_touch ON ep_roll_call_votes;
DROP TRIGGER IF EXISTS trg_ep_roll_call_votes_touch ON ep_roll_call_votes;
CREATE TRIGGER trg_ep_roll_call_votes_touch
    BEFORE UPDATE ON ep_roll_call_votes
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', 'scraped_at', 'created_at');

-- 4. Laws: the two fetch stamps join the derived CELEX parts in the ignore list. Schema
--    only; no row is touched. (The eu_laws data repair of 13-16 Oct is another session's.)
DROP TRIGGER IF EXISTS update_eu_laws_updated_at ON eu_laws;
CREATE TRIGGER update_eu_laws_updated_at
    BEFORE UPDATE ON eu_laws
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed(
        'updated_at', 'celex_year,celex_type,celex_number,eurovoc_fetched_at,body_fetched_at', 'created_at');
