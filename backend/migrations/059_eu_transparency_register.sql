-- 059_eu_transparency_register.sql
-- EU Transparency Register (interest representatives / lobbyists).
-- Source: transparency-register.europa.eu/odplastorganisationxml_en
-- ~17,247 active organisations, ~111 MB XML, refreshed daily by the
-- Joint Transparency Register Secretariat (Commission + Parliament).

CREATE TABLE IF NOT EXISTS eu_transparency_register (
    id                       BIGSERIAL PRIMARY KEY,
    identification_code      VARCHAR(40) NOT NULL UNIQUE,

    -- Registration timestamps
    registration_date        TIMESTAMPTZ,
    last_update_date         TIMESTAMPTZ,

    -- Identity
    original_name            TEXT,
    acronym                  TEXT,
    entity_form              TEXT,
    website_url              TEXT,
    registration_category    VARCHAR(120),

    -- Head office
    head_office_address      TEXT,
    head_office_post_code    VARCHAR(20),
    head_office_city         TEXT,
    head_office_country      VARCHAR(60),
    head_office_phone        VARCHAR(40),

    -- EU office
    eu_office_address        TEXT,
    eu_office_post_code      VARCHAR(20),
    eu_office_city           TEXT,
    eu_office_country        VARCHAR(60),
    eu_office_phone          VARCHAR(40),

    -- Activities (free-text)
    goals                    TEXT,
    eu_legislative_proposals TEXT,
    communication_activities TEXT,
    intergroup_activities    TEXT,
    info_members             TEXT,
    is_member_of             TEXT,
    organisation_members     TEXT,
    interest_represented     TEXT,
    complementary_info       TEXT,

    -- Quantitative data
    members_100_percent      INTEGER,
    members_50_percent       INTEGER,
    members_total            NUMERIC,
    members_fte              NUMERIC,
    ep_accredited_number     INTEGER,

    -- Financial data (most recent closed year)
    financial_year_start     DATE,
    financial_year_end       DATE,
    costs_min                NUMERIC,
    costs_max                NUMERIC,
    grants_total             NUMERIC,
    intermediaries_costs     NUMERIC,
    new_organisation         BOOLEAN,

    -- Multi-valued (parsed into arrays)
    levels_of_interest       TEXT[]   DEFAULT ARRAY[]::TEXT[],
    interests                TEXT[]   DEFAULT ARRAY[]::TEXT[],

    -- v1 body contract — composed from free-text fields
    has_body                 BOOLEAN  NOT NULL DEFAULT false,
    body_html                TEXT,
    body_text                TEXT,
    body_source              VARCHAR(24),

    -- URLs
    public_url               TEXT,

    fetched_at               TIMESTAMPTZ,
    created_at               TIMESTAMPTZ DEFAULT NOW(),
    updated_at               TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_etr_country     ON eu_transparency_register (head_office_country);
CREATE INDEX IF NOT EXISTS idx_etr_category    ON eu_transparency_register (registration_category);
CREATE INDEX IF NOT EXISTS idx_etr_registered  ON eu_transparency_register (registration_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_etr_updated     ON eu_transparency_register (last_update_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_etr_ep_pass     ON eu_transparency_register (ep_accredited_number);
CREATE INDEX IF NOT EXISTS idx_etr_costs       ON eu_transparency_register (costs_max DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_etr_name_search ON eu_transparency_register USING gin (to_tsvector('english', COALESCE(original_name,'') || ' ' || COALESCE(acronym,'')));
CREATE INDEX IF NOT EXISTS idx_etr_interests   ON eu_transparency_register USING gin (interests);

ALTER TABLE eu_transparency_register ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "etr_public_read" ON eu_transparency_register;
CREATE POLICY "etr_public_read" ON eu_transparency_register FOR SELECT USING (true);

COMMENT ON TABLE eu_transparency_register IS
    'EU Transparency Register interest representatives. Source: '
    'transparency-register.europa.eu/odplastorganisationxml_en (daily XML). '
    'Backing table for /api/v1/specialised/transparency-register.';
