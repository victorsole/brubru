-- 071_secondary_acts_regdel_id_body_html.sql
-- 1. Adds regdel_id to secondary_acts so /api/v1/delegated-acts can emit the
--    specific record URL (https://webgate.ec.europa.eu/regdel/#/delegatedActs/
--    <regdel_id>?lang=en) instead of the generic search URL. Populated by
--    backend/scripts/backfill_regdel_ids.py from the regdel /web/delegatedActs
--    payload (cCode → id mapping).
-- 2. Adds body_html so the same endpoint can serve a true HTML body when we
--    can fetch the EUR-Lex Cellar XHTML manifestation (CELEX-bearing acts).

ALTER TABLE secondary_acts
    ADD COLUMN IF NOT EXISTS regdel_id   INTEGER,
    ADD COLUMN IF NOT EXISTS body_html   TEXT,
    ADD COLUMN IF NOT EXISTS body_fetched_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_secondary_acts_regdel_id
    ON secondary_acts (regdel_id) WHERE regdel_id IS NOT NULL;

COMMENT ON COLUMN secondary_acts.regdel_id IS
    'Internal record ID in the Interinstitutional Register of Delegated Acts '
    '(webgate.ec.europa.eu/regdel). When set, the citizen URL is '
    'https://webgate.ec.europa.eu/regdel/#/delegatedActs/<regdel_id>?lang=en';
COMMENT ON COLUMN secondary_acts.body_html IS
    'HTML body of the act (Cellar XHTML manifestation when CELEX is set; '
    'null for PDF-only sources — text_body is the canonical body in that case).';
COMMENT ON COLUMN secondary_acts.body_fetched_at IS
    'Last time the body fields were fetched/refreshed from upstream.';
