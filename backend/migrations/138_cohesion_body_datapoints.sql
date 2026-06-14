-- Migration 138 — add the standard Brubru item datapoints to the cohesion tables.
-- eu_cohesion_finances + eu_cohesion_outcomes were shipped without the 5-datapoint
-- contract (public_url / body_txt / body_html / document_date / creation_date) that
-- every other v2 endpoint carries. This brings them into line: a composed body per
-- row (full on the detail endpoint, null on the list), a canonical public_url, and
-- document_date. creation_date is served from the existing created_at column.

ALTER TABLE eu_cohesion_finances
    ADD COLUMN IF NOT EXISTS public_url    TEXT,
    ADD COLUMN IF NOT EXISTS body_txt      TEXT,
    ADD COLUMN IF NOT EXISTS body_html     TEXT,
    ADD COLUMN IF NOT EXISTS body_source   VARCHAR(24),
    ADD COLUMN IF NOT EXISTS document_date TIMESTAMPTZ;

ALTER TABLE eu_cohesion_outcomes
    ADD COLUMN IF NOT EXISTS public_url    TEXT,
    ADD COLUMN IF NOT EXISTS body_txt      TEXT,
    ADD COLUMN IF NOT EXISTS body_html     TEXT,
    ADD COLUMN IF NOT EXISTS body_source   VARCHAR(24),
    ADD COLUMN IF NOT EXISTS document_date TIMESTAMPTZ;
