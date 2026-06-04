-- 096: Cache of OEIL procedure titles, keyed by OEIL procedure reference.
--
-- Why: the MEP Amendments picker (procedures-by-committee) annotates each
-- procedure with a title from the carriages corpus, but ~203/330 procedures
-- with committee amendments are in-progress proposals not in legislative_carriages
-- (nor committee_work_items / texts_adopted / commission_documents). They showed
-- the bare reference ("2023/0477(COD)") in the picker. OEIL has the real title;
-- this table caches it so we fetch once (Playwright WAF browser) and join cheaply.
--
-- Public-read reference data (public EP titles). Grants follow the Supabase
-- Data API mandate: anon+authenticated SELECT, service_role ALL.

CREATE TABLE IF NOT EXISTS oeil_procedure_titles (
    procedure_ref varchar(50) PRIMARY KEY,
    title         text NOT NULL,
    fetched_at    timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE oeil_procedure_titles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS oeil_procedure_titles_public_read ON oeil_procedure_titles;
CREATE POLICY oeil_procedure_titles_public_read
    ON oeil_procedure_titles FOR SELECT USING (true);

GRANT SELECT ON oeil_procedure_titles TO anon, authenticated;
GRANT ALL ON oeil_procedure_titles TO service_role;
