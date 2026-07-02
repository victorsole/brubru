-- 198_gi_details.sql
-- GI Details + Geographical Area store for the geographical-indications build.
-- One row per EU geographical indication (keyed by file_number, e.g. PGI-ES-A0128),
-- holding the rich profile fields merged from the GIView detail API
-- (tmdn.org/giview/api/geographical-indications/{gid}) and eAmbrosia, plus the
-- extracted "geographical area" (the demarcation), its provenance, and a slot for
-- the geocoded geometry used by the GI maps.
--
-- Populated by a batch job (backend/scripts/extract_gi_geo.py); the /giview
-- endpoint and the maps read from here. Cached, never fetched on-request.
--
-- Coverage is honest: geo_status records whether the area was resolved, is only
-- approximate, has no fetchable source, or the GI is still a pending application.

CREATE TABLE IF NOT EXISTS gi_details (
    id                    BIGSERIAL PRIMARY KEY,
    file_number           VARCHAR(48) NOT NULL UNIQUE,   -- PGI-ES-A0128, PGI-BE+NL+FR+DE-01962
    gi_identifier         VARCHAR(32),                   -- EUGI00000004885 (GIView/eAmbrosia gid)
    protected_name        TEXT,
    gi_type               VARCHAR(8),                    -- PDO / PGI / GI
    product_type          VARCHAR(48),                   -- WINE / FOOD / SPIRIT / AGRICULTURAL PRODUCT
    countries             TEXT[],                        -- {ES} or {BE,NL,FR,DE} for cross-border GIs
    status                VARCHAR(24),                   -- registered / applied / published ...
    eu_protection_date    DATE,

    -- rich profile fields (merged GIView detail + eAmbrosia)
    classification        JSONB,                         -- full CN/HS tree
    legal_instrument      JSONB,                         -- {text, uri}
    publications          JSONB,                         -- [{text, uri}] merged, deduped
    competent_authority   JSONB,                         -- name / address / website

    -- the geographical area (the demarcation)
    geographical_area     TEXT,                          -- extracted demarcation prose
    geo_heading           TEXT,                          -- matched section heading
    geo_source_url        TEXT,                          -- doc the area came from
    geo_source_type       VARCHAR(16),                   -- eurlex / eli / pdf
    geo_confidence        VARCHAR(16),                   -- clean / needs_review / none
    geo_status            VARCHAR(20) NOT NULL DEFAULT 'pending',
                                                         -- resolved / approximate / no_source / pending

    -- geocoding (maps layer; filled in Phase C)
    geo_geometry          JSONB,                         -- GeoJSON geometry
    geo_nuts              TEXT[],                        -- derived NUTS codes
    geo_lau               TEXT[],                        -- derived LAU codes

    raw_giview            JSONB,                         -- cached detail API basicData
    extracted_at          TIMESTAMPTZ,
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gi_details_gid         ON gi_details (gi_identifier);
CREATE INDEX IF NOT EXISTS idx_gi_details_type        ON gi_details (gi_type);
CREATE INDEX IF NOT EXISTS idx_gi_details_product     ON gi_details (product_type);
CREATE INDEX IF NOT EXISTS idx_gi_details_geo_status  ON gi_details (geo_status);
CREATE INDEX IF NOT EXISTS idx_gi_details_countries   ON gi_details USING gin (countries);
CREATE INDEX IF NOT EXISTS idx_gi_details_name        ON gi_details USING gin (to_tsvector('simple', COALESCE(protected_name,'')));

-- Supabase Data API: RLS + public-read policy + explicit grants (mandatory on new public.* tables)
ALTER TABLE gi_details ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS gi_details_public_read ON gi_details;
CREATE POLICY gi_details_public_read ON gi_details FOR SELECT USING (true);

GRANT SELECT ON gi_details TO anon, authenticated;
GRANT ALL    ON gi_details TO service_role;
GRANT USAGE, SELECT ON SEQUENCE gi_details_id_seq TO service_role;
