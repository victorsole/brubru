-- 062_eu_jrc_datasets.sql
-- JRC Data Catalogue index. Source: data.jrc.ec.europa.eu/dataset
-- (Blazor Server SPA, Imperva-WAF-blocked for all /api/* paths and all
-- machine-readable distribution formats; only DOM-scrape via Playwright
-- works). Each entry is one JRC dataset.

CREATE TABLE IF NOT EXISTS eu_jrc_datasets (
    id              BIGSERIAL PRIMARY KEY,
    uuid            VARCHAR(40) NOT NULL UNIQUE,
    title           TEXT,
    description     TEXT,
    public_url      TEXT NOT NULL,

    -- Extra metadata available when a per-dataset detail scrape runs
    publisher       TEXT,
    keywords        TEXT[]    DEFAULT ARRAY[]::TEXT[],
    issued          TIMESTAMPTZ,
    modified        TIMESTAMPTZ,
    distributions   JSONB,

    -- v1 body contract (will be populated by detail scrape)
    has_body        BOOLEAN  NOT NULL DEFAULT false,
    body_html       TEXT,
    body_text       TEXT,
    body_source     VARCHAR(24),

    listing_page    INTEGER,
    fetched_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ejrc_title    ON eu_jrc_datasets USING gin (to_tsvector('english', COALESCE(title,'')));
CREATE INDEX IF NOT EXISTS idx_ejrc_keywords ON eu_jrc_datasets USING gin (keywords);
CREATE INDEX IF NOT EXISTS idx_ejrc_modified ON eu_jrc_datasets (modified DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_ejrc_has_body ON eu_jrc_datasets (has_body);

ALTER TABLE eu_jrc_datasets ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "ejrc_public_read" ON eu_jrc_datasets;
CREATE POLICY "ejrc_public_read" ON eu_jrc_datasets FOR SELECT USING (true);

COMMENT ON TABLE eu_jrc_datasets IS
    'JRC Data Catalogue index. Source: data.jrc.ec.europa.eu/dataset '
    '(Blazor Server SPA; only Playwright DOM scrape works — Imperva WAF '
    'blocks all REST and RDF distribution endpoints). Backing table for '
    '/api/v1/specialised/jrc-datasets.';
