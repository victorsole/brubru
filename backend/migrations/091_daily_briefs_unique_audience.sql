-- Migration 091: replace uq_daily_briefs_date_url with a 3-column key that
-- includes audience. Same-day, same-URL is fine across tenants.
--
-- Driver: the EFPIA tenant brief shares some Brubru-internal URLs with the
-- public daily brief (e.g. https://brubru.beresol.eu/my-eu-bubble?tab=legislative).
-- The original unique constraint is too strict for multi-tenant rows.

ALTER TABLE daily_briefs DROP CONSTRAINT IF EXISTS uq_daily_briefs_date_url;
DROP INDEX IF EXISTS uq_daily_briefs_date_url;

ALTER TABLE daily_briefs
    ADD CONSTRAINT uq_daily_briefs_date_url_audience
    UNIQUE (brief_date, url, audience);
