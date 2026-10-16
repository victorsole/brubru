-- 302: eu_laws keeps each kind of date apart, and the change-signal switch is scoped to one transaction.
--
-- Audit of 299 (16 Oct 2026, before the backfill ran): the Publications Office types every
-- resource_legal_date_entry-into-force date (authority table fd_335: EV entry into force, MA application,
-- MA/PART partial application, PE effect). Over the 30,246 export folders with text: EV 23,799 dates, MA 5,069,
-- PE 4,038, MA/PART 169, a date carrying two types 439, untyped 84 (plus 4 typed V). One list would tell a client
-- that GDPR entered into force on 25 May 2018 (its application date) and give the AI Act five entry-into-force
-- dates (one is). So entry_into_force keeps the EV dates and the untyped ones (the property names them so);
-- application_dates (MA, MA/PART) and effect_dates (PE) hold the others. A date with two types sits in both.
--
-- The switch of 299 compared the setting with 'on'; a plain SET (not SET LOCAL) on a pooled connection would then
-- stop updated_at moving on all 29 tables until the connection closed. It now compares with the transaction id.
-- The migration numbers 291-293 of this work were renumbered 299-301 (origin/main holds other 291-297, and 298 is
-- reserved by the API session); the comments below restate them.

SET LOCAL lock_timeout = '10s';

ALTER TABLE eu_laws
    ADD COLUMN IF NOT EXISTS application_dates date[],
    ADD COLUMN IF NOT EXISTS effect_dates date[];

COMMENT ON COLUMN eu_laws.entry_into_force IS 'Dates of entry into force in the metadata: resource_legal_date_entry-into-force typed EV (fd_335), or untyped (302).';
COMMENT ON COLUMN eu_laws.application_dates IS 'Dates from which the act applies: typed MA or MA/PART (fd_335) (302).';
COMMENT ON COLUMN eu_laws.effect_dates IS 'Dates of effect: typed PE (fd_335) (302).';
COMMENT ON COLUMN eu_laws.eli IS 'The ELI the metadata states on the work (resource_legal_eli; one per publication or none) (302).';
COMMENT ON COLUMN eu_laws.procedures IS 'Interinstitutional procedure numbers YYYY/NNNN (the OEIL reference without its type): the export''s work_part_of_dossier, else Cellar''s dossier_contains_work (302).';
COMMENT ON COLUMN eu_laws.alias IS 'Common name of the law (e.g. General Data Protection Regulation): Brubru''s curated list backend/data/leg_2026-10_table/aliases.csv, never derived (301).';
COMMENT ON COLUMN eu_laws.acronym IS 'Acronym of the alias (e.g. GDPR), from the same curated list (301).';
COMMENT ON COLUMN eu_laws.celex_number IS 'The CELEX string''s number part, derived by trigger eu_laws_celex_parts (migration 299); for type A agreements a date (MMDD); not always the act''s natural number; not unique.';
COMMENT ON COLUMN eu_laws.celex_year IS 'The CELEX string''s year part, derived by trigger eu_laws_celex_parts (migration 299).';
COMMENT ON COLUMN eu_laws.celex_type IS 'The CELEX string''s one-letter type, derived by trigger eu_laws_celex_parts (migration 299); NULL when the type has two letters.';
COMMENT ON INDEX uq_eu_laws_celex IS 'One eu_laws row per CELEX (migration 300, 15 Oct 2026); NULL and empty CELEX are not compared.';

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

    -- A backfill that adds facts a row always had, not a change of the record, sets
    -- brubru.keep_change_signal to its own transaction id (set_config(..., txid_current()::text, true)):
    -- the signal columns then keep OLD's value. Scoped to that transaction id (302), so a value left
    -- on a pooled connection by a plain SET can never silence the signal of a later transaction.
    -- An OLD without a signal is seeded from NEW, as below (272).
    IF current_setting('brubru.keep_change_signal', true) = txid_current()::text THEN
        NEW := jsonb_populate_record(NEW, (
            SELECT jsonb_object_agg(c, coalesce(nullif(to_jsonb(OLD) -> c, 'null'::jsonb), to_jsonb(NEW) -> c))
            FROM unnest(signal_cols) c));
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
