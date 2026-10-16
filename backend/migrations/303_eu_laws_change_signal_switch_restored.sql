-- 303: restore the transaction-scoped change-signal switch of 302 on top of the live brubru_touch_if_changed.
--
-- 302 (applied 16 Oct 2026, 13:05 CEST, then numbered 300) scoped the switch to the transaction id and seeded a NULL signal under it.
-- The API session's migration 297 (applied 15:01 CEST) then replaced the function with a text built on 301: it adds the
-- brubru_change_log write and keeps 301's plain 'on' switch, so a backfill setting the transaction id no longer kept
-- updated_at (the eu_laws metadata backfill's own check stopped it; nothing was written). This is the live text read
-- with pg_get_functiondef at 15:05 CEST, change log and all, with only the switch block replaced. Any later
-- CREATE OR REPLACE of this function must start from pg_get_functiondef, not from a file.

SET LOCAL lock_timeout = '10s';

-- Stop if the function changed after this file was written: never overwrite a newer text. Two texts are accepted:
-- the API session's 297 (live when this was applied, 16 Oct 2026) and 302's (what a replay of the migrations in
-- number order holds here, since 297 sorts before 299-302 although it was applied after them).
DO $guard$
BEGIN
    IF md5(pg_get_functiondef('brubru_touch_if_changed'::regproc)) NOT IN ('eb956a94afc16c4c690cbb54b4bf53c0',
                                                                         'cc040401522bc991418a4b932cae8432') THEN
        RAISE EXCEPTION 'brubru_touch_if_changed changed since 301 was written: rebuild 301 from the live text';
    END IF;
END
$guard$;

CREATE OR REPLACE FUNCTION public.brubru_touch_if_changed()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
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

    -- A backfill that adds facts a row always had, not a change of the record, sets
    -- brubru.keep_change_signal to its own transaction id (set_config(..., txid_current()::text, true)):
    -- the signal columns then keep OLD's value and nothing is logged. Scoped to that transaction id, so
    -- a value left on a pooled connection by a plain SET can never silence a later transaction (300,
    -- restored in 303). An OLD without a signal is seeded from NEW, as below (272).
    IF current_setting('brubru.keep_change_signal', true) = txid_current()::text THEN
        NEW := jsonb_populate_record(NEW, (
            SELECT jsonb_object_agg(c, coalesce(nullif(to_jsonb(OLD) -> c, 'null'::jsonb), to_jsonb(NEW) -> c))
            FROM unnest(signal_cols) c));
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
$function$;
