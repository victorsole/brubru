-- Migration 139 — eu_solidarity_fund
-- EU Solidarity Fund (EUSF) disaster cases 2002-2021, from the DG REGIO Cohesion
-- Open Data Platform (Socrata 7a49-av34). One row per disaster case: country,
-- disaster type, accepted direct damage, EUSF grant paid. Amounts in EUR million.
-- Backs /api/v2/funding/eusf. Follows the standard v2 item contract (5 datapoints
-- + composed body). Full-refresh backfill; weekly tier.

CREATE TABLE IF NOT EXISTS eu_solidarity_fund (
    id                         BIGSERIAL PRIMARY KEY,
    year_of_occurrence         INTEGER,
    cci_number                 TEXT,
    applicant_country          TEXT,
    name_of_disaster           TEXT,
    disaster_type              TEXT,
    status                     TEXT,
    category                   TEXT,         -- Major / Regional / Neighbouring
    first_damage_date          DATE,
    date_of_initial_application TEXT,
    total_direct_damage_meur   NUMERIC,      -- accepted total direct damage, EUR million
    eligible_emergency_cost_meur NUMERIC,    -- cost of eligible emergency operations, EUR million
    damage_pct                 NUMERIC,      -- eligible cost as % of total damage
    eusf_grant_paid_meur       NUMERIC,      -- EUSF grant paid, EUR million
    -- standard datapoints
    public_url                 TEXT,
    body_txt                   TEXT,
    body_html                  TEXT,
    body_source                VARCHAR(24),
    document_date              TIMESTAMPTZ,
    raw                        JSONB,
    fetched_at                 TIMESTAMPTZ DEFAULT NOW(),
    created_at                 TIMESTAMPTZ DEFAULT NOW(),
    updated_at                 TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_eusf_country ON eu_solidarity_fund (applicant_country);
CREATE INDEX IF NOT EXISTS ix_eusf_type    ON eu_solidarity_fund (disaster_type);
CREATE INDEX IF NOT EXISTS ix_eusf_year    ON eu_solidarity_fund (year_of_occurrence);

ALTER TABLE eu_solidarity_fund ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS p_eusf_read ON eu_solidarity_fund;
CREATE POLICY p_eusf_read ON eu_solidarity_fund FOR SELECT TO anon, authenticated USING (true);
GRANT SELECT ON eu_solidarity_fund TO anon, authenticated;
GRANT ALL    ON eu_solidarity_fund TO service_role;
GRANT USAGE, SELECT ON SEQUENCE eu_solidarity_fund_id_seq TO service_role;
