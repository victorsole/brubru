-- 060_eu_cohesion_datasets.sql
-- DG REGIO Cohesion Open Data Platform catalog. Datasets are Socrata
-- views at cohesiondata.ec.europa.eu/api/views.json — covering ESF+,
-- ERDF, Cohesion Fund, Interreg, JTF allocations, indicators,
-- categorisation, and progress reporting for the 2014-2020 and
-- 2021-2027 programming periods.

CREATE TABLE IF NOT EXISTS eu_cohesion_datasets (
    id              BIGSERIAL PRIMARY KEY,
    socrata_id      VARCHAR(20) NOT NULL UNIQUE,
    name            TEXT,
    description     TEXT,
    category        TEXT,
    tags            TEXT[]   DEFAULT ARRAY[]::TEXT[],
    attribution     TEXT,
    download_count  INTEGER,
    view_count      INTEGER,
    row_count       INTEGER,
    last_updated_at TIMESTAMPTZ,
    created_at_src  TIMESTAMPTZ,
    columns         JSONB,
    public_url      TEXT,
    api_endpoint    TEXT,

    -- v1 body contract
    has_body        BOOLEAN  NOT NULL DEFAULT false,
    body_html       TEXT,
    body_text       TEXT,
    body_source     VARCHAR(24),

    fetched_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ecd_category ON eu_cohesion_datasets (category);
CREATE INDEX IF NOT EXISTS idx_ecd_views    ON eu_cohesion_datasets (view_count DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_ecd_updated  ON eu_cohesion_datasets (last_updated_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_ecd_search   ON eu_cohesion_datasets USING gin (to_tsvector('english', COALESCE(name,'') || ' ' || COALESCE(description,'')));
CREATE INDEX IF NOT EXISTS idx_ecd_tags     ON eu_cohesion_datasets USING gin (tags);

ALTER TABLE eu_cohesion_datasets ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "ecd_public_read" ON eu_cohesion_datasets;
CREATE POLICY "ecd_public_read" ON eu_cohesion_datasets FOR SELECT USING (true);

COMMENT ON TABLE eu_cohesion_datasets IS
    'DG REGIO Cohesion Open Data Platform catalogue (Socrata at '
    'cohesiondata.ec.europa.eu). Backing table for /api/v1/specialised/cohesion-datasets. '
    'Body composed from dataset description + column list. The actual '
    'tabular data stays in Socrata — partners follow api_endpoint.';
