-- 277: when a procedure's OEIL page answers 404, say so, and keep the row out of the API.
--
-- /oeil/procedures served 15 procedures whose OEIL page does not exist (7 Oct 2026):
-- references OEIL never issued or no longer has (2026/2705(RSP) where OEIL holds the same
-- resolution as 2026/2596(RSP)), Legislative Train references Brubru derived
-- (2020/0297(COD)), and new resolutions OEIL has not published yet. Each went out with a
-- public_url that 404s and no body. The status updater already treated 404 as "not on
-- OEIL yet" but only stamped the fetch time, so nothing downstream could tell.
--
-- Set on a 404, cleared when the page answers again; the warm-tier updater re-checks it.
ALTER TABLE legislative_carriages
    ADD COLUMN IF NOT EXISTS oeil_missing_since timestamptz;

COMMENT ON COLUMN legislative_carriages.oeil_missing_since IS
    'First 404 from the OEIL procedure page in the current run of 404s; NULL when the page exists. Rows with a value are not served.';

CREATE INDEX IF NOT EXISTS idx_carriages_oeil_missing
    ON legislative_carriages (oeil_missing_since) WHERE oeil_missing_since IS NOT NULL;
