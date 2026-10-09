-- 285: committee reports tabled for a plenary vote get their own table, out of texts_adopted.
--
-- /parliament/plenary-tabled-texts (renamed from /texts-submitted on 8 Oct 2026) read
-- texts_adopted WHERE adoption_date IS NULL: 36 committee REPORTS (A10/YYYY/NNNN) written
-- there on purpose by scripts/ingest_texts_submitted.py. A report is not an adopted text,
-- and sharing the table is how the resolutions list once served a draft report as the
-- adopted resolution (2025/2039(INI), 2025/2210(INI)).
--
-- Same shape as texts_adopted (LIKE), so the endpoint serves the same item. The 36 rows
-- MOVE WITH THEIR ids: GovClipping identifies documents by id (9 Oct 2026). No user
-- tracks any of them (user_text_adopted_tracks would cascade). Approved by Victor on
-- 8 Oct 2026 as part of the rename; filling the table from EP Open Data comes later.
BEGIN;

CREATE TABLE IF NOT EXISTS plenary_tabled_texts
    (LIKE texts_adopted INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES);

ALTER TABLE plenary_tabled_texts
    ADD CONSTRAINT plenary_tabled_texts_legislative_carriage_id_fkey
    FOREIGN KEY (legislative_carriage_id) REFERENCES legislative_carriages(id);

ALTER TABLE plenary_tabled_texts ENABLE ROW LEVEL SECURITY;
CREATE POLICY plenary_tabled_texts_public_read ON plenary_tabled_texts
    FOR SELECT TO anon, authenticated USING (true);
GRANT SELECT ON plenary_tabled_texts TO anon, authenticated;
GRANT ALL ON plenary_tabled_texts TO service_role;

CREATE TRIGGER trg_plenary_tabled_texts_touch BEFORE UPDATE ON plenary_tabled_texts
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen');

COMMENT ON TABLE plenary_tabled_texts IS
    'Documents tabled for a plenary vote (committee reports A10/YYYY/NNNN). Served by /api/v2/parliament/plenary-tabled-texts. Writer: scripts/ingest_texts_submitted.py.';

INSERT INTO plenary_tabled_texts
SELECT * FROM texts_adopted WHERE ta_reference !~ '^P[0-9]+_TA';

DO $$
DECLARE moved int; src int;
BEGIN
    SELECT count(*) INTO moved FROM plenary_tabled_texts;
    SELECT count(*) INTO src FROM texts_adopted WHERE ta_reference !~ '^P[0-9]+_TA';
    IF moved <> src OR moved = 0 THEN
        RAISE EXCEPTION 'move mismatch: % copied, % in texts_adopted', moved, src;
    END IF;
END $$;

DELETE FROM texts_adopted WHERE ta_reference !~ '^P[0-9]+_TA';

COMMIT;
