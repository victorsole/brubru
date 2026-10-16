-- 299: eu_laws.celex_year, celex_type and celex_number are derived from celex, in one place.
--
-- The three columns were a copy of the identifier that no writer kept in step. Measured 14 Oct 2026:
-- 2,381 rows blank (fill_celex_from_mtd.py split with a pattern that rejects every suffixed CELEX;
-- import_corpus_update.py inserts rows without them) and 2,074 wrong (older imports took them from the
-- document text; later CELEX corrections left them stale: 1,771 differed in type only, 81 in year and
-- number). fix_eu_laws_celex_parts.py corrected the rows; an independent audit then showed the writers
-- would undo it on the next import. So the database derives them: no writer can set them wrongly again.
--
-- Rule (sector 3 only, the only shape a CHAR(1) type can hold): 3 + year + one letter + number (1 to 6
-- digits), an optional sequence suffix "(NN)" and corrigendum suffixes "R(NN)". The parts are those of
-- the CELEX string: "the CELEX's number", which for type A agreements is a date (MMDD) and is not
-- always the act's natural number (32018O0003 stores 3; the act is 2018/570). The three parts are not
-- a key: 32023D0161 and 32023D00161 split alike. Anything else (sector 5 "XG", no CELEX) gets NULLs.
--
-- The change signal ignores the three columns: they follow celex, so a change of celex already moves
-- updated_at, and recomputing them must never report a row as changed to a ?updated_from= caller
-- (the 14 Oct correction moved updated_at on 4,455 rows whose served payload did not change).

CREATE OR REPLACE FUNCTION eu_laws_derive_celex_parts()
RETURNS TRIGGER AS $$
DECLARE
    m text[];
BEGIN
    m := regexp_match(coalesce(NEW.celex, ''), '^3([0-9]{4})([A-Z])([0-9]{1,6})(?:\([0-9]{2}\))?(?:R\([0-9]{2}\))*$');
    IF m IS NULL THEN
        NEW.celex_year := NULL;
        NEW.celex_type := NULL;
        NEW.celex_number := NULL;
    ELSE
        NEW.celex_year := m[1]::int;
        NEW.celex_type := m[2];
        NEW.celex_number := m[3]::int;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- BEFORE triggers fire in name order: "eu_laws_celex_parts" runs before "update_eu_laws_updated_at".
DROP TRIGGER IF EXISTS eu_laws_celex_parts ON eu_laws;
CREATE TRIGGER eu_laws_celex_parts
    BEFORE INSERT OR UPDATE ON eu_laws
    FOR EACH ROW EXECUTE FUNCTION eu_laws_derive_celex_parts();

DROP TRIGGER IF EXISTS update_eu_laws_updated_at ON eu_laws;
CREATE TRIGGER update_eu_laws_updated_at
    BEFORE UPDATE ON eu_laws
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', 'celex_year,celex_type,celex_number', 'created_at');

COMMENT ON COLUMN eu_laws.celex_number IS 'The CELEX string''s number part, derived by trigger eu_laws_celex_parts (migration 299); for type A agreements a date (MMDD); not always the act''s natural number; not unique.';
COMMENT ON COLUMN eu_laws.celex_year IS 'The CELEX string''s year part, derived by trigger eu_laws_celex_parts (migration 299).';
COMMENT ON COLUMN eu_laws.celex_type IS 'The CELEX string''s one-letter type, derived by trigger eu_laws_celex_parts (migration 299); NULL when the type has two letters.';
