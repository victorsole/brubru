-- 068_commission_calendar_urls_body.sql
-- Adds body + datapoint columns to commission_calendar_urls so the live
-- /api/v1/commissioners/{name}/agenda endpoint can serve the 5 mandatory
-- Brubru v1 datapoints from cache without re-scraping detail pages on every
-- request.

ALTER TABLE commission_calendar_urls
    ADD COLUMN IF NOT EXISTS body_text       TEXT,
    ADD COLUMN IF NOT EXISTS body_html       TEXT,
    ADD COLUMN IF NOT EXISTS body_fetched_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_commission_calendar_urls_has_body
    ON commission_calendar_urls ((body_text IS NOT NULL));

COMMENT ON COLUMN commission_calendar_urls.body_text IS
    'Plain-text body of the agenda event detail page (commission.europa.eu). '
    'Populated by backfill_commissioner_agenda_bodies.py; null until detail '
    'page is fetched.';
COMMENT ON COLUMN commission_calendar_urls.body_html IS
    'HTML body of the agenda event detail page (raw, lightly cleaned).';
COMMENT ON COLUMN commission_calendar_urls.body_fetched_at IS
    'When body_text/body_html were last fetched. Distinct from first_seen_at '
    '(URL discovery) and last_seen_at (URL refresh).';
