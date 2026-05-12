-- 070_legislative_carriages_oeil_body.sql
-- Adds cached OEIL procedure-file body to legislative_carriages so the v1
-- /committees/{code}/work-items endpoint can serve body_txt / body_html
-- without re-scraping the OEIL page on every request.
--
-- Populated by backend/scripts/backfill_oeil_body.py (run-once + cron).

ALTER TABLE legislative_carriages
    ADD COLUMN IF NOT EXISTS oeil_html_body       TEXT,
    ADD COLUMN IF NOT EXISTS oeil_text_body       TEXT,
    ADD COLUMN IF NOT EXISTS oeil_body_fetched_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_legislative_carriages_has_oeil_body
    ON legislative_carriages ((oeil_text_body IS NOT NULL));

COMMENT ON COLUMN legislative_carriages.oeil_html_body IS
    'Cleaned HTML body of the OEIL procedure-file page (sections 1-6: Basic '
    'info, Key players, Key events, Technical info, Documentation gateway, '
    'Additional info). Source: https://oeil.europarl.europa.eu/oeil/en/'
    'procedure-file?reference=<oeil_procedure_ref>';
COMMENT ON COLUMN legislative_carriages.oeil_text_body IS
    'Plain-text rendering of oeil_html_body (HTML stripped, whitespace '
    'collapsed). Used as body_txt in /committees/{code}/work-items.';
COMMENT ON COLUMN legislative_carriages.oeil_body_fetched_at IS
    'Timestamp of the last successful OEIL body fetch. Null when never fetched.';
