-- 272: updated_at is never null on economy_items / eu_news_items (Victor's hard rule, 5 Oct 2026:
-- every API item carries updated_date).
--
-- Two holes. 271 added updated_at with no default, and brubru_touch_if_changed returns NEW
-- untouched on INSERT, so every row inserted since was born null (6,203 of October's 9,145).
-- And the trigger's "nothing changed" branch restores OLD's signal value, so a backfill that
-- sets only updated_at is silently reverted to null.
--
-- Fix: a default for new rows, and the trigger keeps OLD's value only when OLD has one.
-- Existing nulls are seeded in batches by scripts/seed_updated_at_nulls.py, never here.
ALTER TABLE economy_items ALTER COLUMN updated_at SET DEFAULT now();
ALTER TABLE eu_news_items ALTER COLUMN updated_at SET DEFAULT now();

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
        -- Keep OLD's signal, unless OLD has none: then the caller's value seeds it (272).
        patch := (SELECT jsonb_object_agg(c, coalesce(nullif(to_jsonb(OLD) -> c, 'null'::jsonb),
                                                      to_jsonb(NEW) -> c))
                  FROM unnest(signal_cols) c);
    END IF;

    NEW := jsonb_populate_record(NEW, patch);
    RETURN NEW;
END;
$function$;
