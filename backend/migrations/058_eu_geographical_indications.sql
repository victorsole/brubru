-- 058_eu_geographical_indications.sql (REVISION B — eAmbrosia + GIview)
--
-- Backing table for /api/v1/specialised/gi.
--
-- Two upstream sources (both confirmed working with browser User-Agent):
--   1. eAmbrosia API at webgate.ec.europa.eu/eambrosia-api/api/v1/
--      Authoritative EU GI register (3,994 records). Deep per-record
--      detail: producer group, competent authorities, summary sheet
--      attachments, sustainability reports, CN classification, etc.
--   2. GIview union_register at tmdn.org/giview/api/search/union_register
--      EUIPO-managed broader register (5,809 records). Includes
--      pending applications and additional third-country GIs.
--
-- Records share the EUGIxxxxxxxxxx identifier across both sources. The
-- backfill UPSERTs eAmbrosia first (richer data) then merges in GIview-
-- only records.

CREATE TABLE IF NOT EXISTS eu_geographical_indications (
    id                  BIGSERIAL PRIMARY KEY,
    gi_identifier       VARCHAR(40) NOT NULL UNIQUE,

    -- Names + identification
    protected_names     TEXT[]   DEFAULT ARRAY[]::TEXT[],
    file_number         VARCHAR(60),

    -- Geography
    countries           TEXT[]   DEFAULT ARRAY[]::TEXT[],
    third_country_flag  BOOLEAN,
    map_locations       JSONB,

    -- Classification
    gi_type             VARCHAR(20),
    product_type        VARCHAR(50),
    product_categories  JSONB,
    cn_classification   JSONB,

    -- Status + dates
    status              VARCHAR(40),
    eu_protection_date  DATE,
    modification_date   TIMESTAMPTZ,
    amendments_in_progress BOOLEAN,
    removed_flag        BOOLEAN,

    -- Legal basis + publications
    legal_instrument    JSONB,
    publications        JSONB,
    single_document     JSONB,
    summary_sheets      JSONB,
    transcriptions      JSONB,
    amendments          JSONB,

    -- Producer group
    producer_group_name      TEXT,
    producer_group_email     TEXT,
    producer_group_phone     VARCHAR(50),
    producer_group_url       TEXT,
    producer_group_address   TEXT,
    producer_group_country   VARCHAR(8),
    producer_group_updated_on TIMESTAMPTZ,

    -- Authorities + sustainability
    competent_control_authorities JSONB,
    recognised_producers_group    JSONB,
    sustainability_reports        JSONB,

    -- Source indicators
    source              VARCHAR(20)  NOT NULL DEFAULT 'eambrosia',  -- eambrosia / giview / merged
    giview_source       VARCHAR(20),
    giview_database     VARCHAR(60),

    -- Source URLs
    eambrosia_url       TEXT,
    eurlex_url          TEXT,
    public_url          TEXT,

    -- v1 body contract (composed from single_document or summary_sheets)
    has_body            BOOLEAN  NOT NULL DEFAULT false,
    body_html           TEXT,
    body_text           TEXT,
    body_source         VARCHAR(24),

    fetched_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_egi_gi_type    ON eu_geographical_indications (gi_type);
CREATE INDEX IF NOT EXISTS idx_egi_status     ON eu_geographical_indications (status);
CREATE INDEX IF NOT EXISTS idx_egi_protect    ON eu_geographical_indications (eu_protection_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_egi_modified   ON eu_geographical_indications (modification_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_egi_product    ON eu_geographical_indications (product_type);
CREATE INDEX IF NOT EXISTS idx_egi_3rd_country ON eu_geographical_indications (third_country_flag);
CREATE INDEX IF NOT EXISTS idx_egi_countries  ON eu_geographical_indications USING gin (countries);
CREATE INDEX IF NOT EXISTS idx_egi_names      ON eu_geographical_indications USING gin (protected_names);
CREATE INDEX IF NOT EXISTS idx_egi_file_num   ON eu_geographical_indications (file_number);
CREATE INDEX IF NOT EXISTS idx_egi_source     ON eu_geographical_indications (source);

ALTER TABLE eu_geographical_indications ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "egi_public_read" ON eu_geographical_indications;
CREATE POLICY "egi_public_read" ON eu_geographical_indications FOR SELECT USING (true);

COMMENT ON TABLE eu_geographical_indications IS
    'EU Geographical Indications. Source 1: eAmbrosia API at '
    'webgate.ec.europa.eu/eambrosia-api (DG AGRI, authoritative). '
    'Source 2: GIview union_register at tmdn.org/giview (EUIPO, broader). '
    'Backing table for /api/v1/specialised/gi.';
