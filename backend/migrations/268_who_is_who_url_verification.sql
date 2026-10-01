-- 268: record whether an official's Whoiswho page actually exists.
--
-- GovClipping reported on 1 October 2026 that who-is-who URLs led to pages that
-- do not exist. The first fix pointed every official at their own person page and
-- was verified on 6 officials, 6/6 returning 200. Measured properly afterwards,
-- roughly 4,400 of 17,777 (~25%) 404: whole families (COR, ERCEA, EIB) have no
-- published person pages at all, while others are partial (EESC 1 in 10 works,
-- HADEA 5 in 10). The person id carries no signal for this and the SPARQL source
-- does not say, so existence can only be established by asking the page itself.
--
-- These two columns hold that answer so it is asked once per official rather than
-- guessed, and so the nightly ingest cannot resurrect a URL already proven dead.
ALTER TABLE who_is_who_officials
    ADD COLUMN IF NOT EXISTS url_status     integer,
    ADD COLUMN IF NOT EXISTS url_checked_at timestamptz;

COMMENT ON COLUMN who_is_who_officials.url_status IS
    'HTTP status last returned by public_url. 200 = the page exists. 404 = it does not, and public_url is nulled. NULL = never checked.';
COMMENT ON COLUMN who_is_who_officials.url_checked_at IS
    'When url_status was last established. Drives the resumable drain and periodic re-checks.';

-- The drain picks unchecked rows first, then the stalest. Without this index that
-- ordering is a sequential scan of 18,377 rows on every batch.
CREATE INDEX IF NOT EXISTS idx_who_is_who_url_checked
    ON who_is_who_officials (url_checked_at NULLS FIRST)
    WHERE person_uri IS NOT NULL;
