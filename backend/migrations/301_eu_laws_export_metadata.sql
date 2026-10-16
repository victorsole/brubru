-- 301: eu_laws carries the Publications Office's own metadata for each law; a backfill can add it without moving updated_at.
--
-- Victor, 16 Oct 2026: "05 eur-lex/laws" serves the LEG_2026-10 export's datapoints. Stored here: alias and acronym
-- (aliases.csv, the only source; 17 and 16 laws today), the creating bodies, the in-force flag, the ELI, the dates of
-- entry into force and the interinstitutional procedure numbers. Sector, year, number, document type and the act a
-- corrigendum corrects are read from the CELEX when a law is served (services/celex_types.py) and need no column.
-- Writers, one per source of rows: fill_eu_laws_export_metadata.py for the laws the export describes (from the
-- tables built from its metadata, backend/data/leg_2026-10_table/), import_corpus_update.py for later exports, and
-- the daily OJ sync for the acts it adds (not yet: step 5).
--
-- Victor's choice, 16 Oct 2026: filling these facts is not a change of the record, so a client syncing by
-- updated_from must not receive 30,000 laws again. brubru_touch_if_changed (29 tables) gains a switch that only a
-- session setting SET LOCAL brubru.keep_change_signal = 'on' turns on; the function is otherwise the live text
-- (272). A law that leaves force later is still a change.

SET LOCAL lock_timeout = '10s';

ALTER TABLE eu_laws
    ADD COLUMN IF NOT EXISTS alias text,
    ADD COLUMN IF NOT EXISTS acronym text,
    ADD COLUMN IF NOT EXISTS authors text[],
    ADD COLUMN IF NOT EXISTS in_force boolean,
    ADD COLUMN IF NOT EXISTS eli text,
    ADD COLUMN IF NOT EXISTS entry_into_force date[],
    ADD COLUMN IF NOT EXISTS procedures text[];

COMMENT ON COLUMN eu_laws.alias IS 'Common name of the law (e.g. General Data Protection Regulation), from backend/data/leg_2026-10_table/aliases.csv only; never derived (301).';
COMMENT ON COLUMN eu_laws.acronym IS 'Acronym of the alias (e.g. GDPR), from aliases.csv only (301).';
COMMENT ON COLUMN eu_laws.authors IS 'Publications Office corporate-body codes of the bodies that created the act (work_created_by_agent: COM, CONSIL, EP, a DG...) (301).';
COMMENT ON COLUMN eu_laws.in_force IS 'The act''s in-force flag in the Publications Office metadata (resource_legal_in-force); NULL when the metadata carries none, which is not false (301).';
COMMENT ON COLUMN eu_laws.eli IS 'The ELI URI of this publication from its metadata; NULL when none or several match the act (301).';
COMMENT ON COLUMN eu_laws.entry_into_force IS 'Dates of entry into force stated in the metadata (resource_legal_date_entry-into-force); several mean staged entry into force (301).';
COMMENT ON COLUMN eu_laws.procedures IS 'Interinstitutional procedure numbers YYYY/NNNN the metadata links the act to (the OEIL reference without its type); internal ids left out (301).';

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

    -- A backfill that adds facts a row always had, not a change of the record, runs with
    -- SET LOCAL brubru.keep_change_signal = 'on': the signal columns keep OLD's value (301).
    -- Nothing else sets it, so every other writer still moves the signal.
    IF current_setting('brubru.keep_change_signal', true) = 'on' THEN
        NEW := jsonb_populate_record(NEW, (
            SELECT jsonb_object_agg(c, to_jsonb(OLD) -> c) FROM unnest(signal_cols) c));
        RETURN NEW;
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
