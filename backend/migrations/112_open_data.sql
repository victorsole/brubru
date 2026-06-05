-- Migration 112 — data.europa.eu open data (API v2 "Open Data" folder)
--
-- Backing store for the Open Data domain, ingested from the data.europa.eu open
-- JSON API (the EU Publications Office open-data portal — 1.9M+ datasets across
-- ~90 catalogues). The search API returns full DCAT records, so one row per
-- dataset holds everything; `is_hvd` flags High-Value Datasets (Open Data
-- Directive). ELDS (legal data space) and PPDS (procurement data space) are
-- catalogues inside the same portal.
--
-- Bodies composed at ingest, so the API never calls data.europa.eu on the
-- request path. Public reference data: anon + authenticated SELECT, service_role ALL.

BEGIN;

CREATE TABLE IF NOT EXISTS open_data_datasets (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id    TEXT NOT NULL UNIQUE,        -- data.europa.eu record id

    title         TEXT NOT NULL,
    description   TEXT,
    publisher     TEXT,
    catalogue     TEXT,                         -- catalog id
    country       TEXT,
    country_code  TEXT,
    themes        TEXT[] DEFAULT '{}',
    keywords      TEXT[] DEFAULT '{}',
    formats       TEXT[] DEFAULT '{}',          -- distribution formats (CSV, JSON, ...)
    is_hvd        BOOLEAN DEFAULT FALSE,         -- High-Value Dataset
    distributions JSONB DEFAULT '[]'::jsonb,     -- [{format, url, title}] download links
    quality_score NUMERIC,

    public_url    TEXT,                          -- data.europa.eu dataset page
    body_txt      TEXT,
    body_html     TEXT,
    issued        DATE,
    modified      DATE,                          -- document_date

    source_url    TEXT,
    first_seen    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_opendata_publisher ON open_data_datasets (publisher);
CREATE INDEX IF NOT EXISTS ix_opendata_catalogue ON open_data_datasets (catalogue);
CREATE INDEX IF NOT EXISTS ix_opendata_country   ON open_data_datasets (country_code);
CREATE INDEX IF NOT EXISTS ix_opendata_hvd       ON open_data_datasets (is_hvd);
CREATE INDEX IF NOT EXISTS ix_opendata_modified  ON open_data_datasets (modified DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS ix_opendata_themes    ON open_data_datasets USING GIN (themes);

CREATE TABLE IF NOT EXISTS open_data_catalogues (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    catalogue_id   TEXT NOT NULL UNIQUE,
    title          TEXT,
    country        TEXT,
    dataset_count  INTEGER,
    public_url     TEXT,
    body_txt       TEXT,
    body_html      TEXT,
    first_seen     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetched_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_opendata_cat_country ON open_data_catalogues (country);

ALTER TABLE open_data_datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE open_data_catalogues ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS open_data_datasets_public_read ON open_data_datasets;
CREATE POLICY open_data_datasets_public_read ON open_data_datasets
    FOR SELECT TO anon, authenticated USING (true);
DROP POLICY IF EXISTS open_data_catalogues_public_read ON open_data_catalogues;
CREATE POLICY open_data_catalogues_public_read ON open_data_catalogues
    FOR SELECT TO anon, authenticated USING (true);

GRANT SELECT ON open_data_datasets TO anon, authenticated;
GRANT ALL ON open_data_datasets TO service_role;
GRANT SELECT ON open_data_catalogues TO anon, authenticated;
GRANT ALL ON open_data_catalogues TO service_role;

COMMIT;
