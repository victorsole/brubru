-- Migration 136 — eu_cohesion_finances
-- Per-fund finance / allocation rows from the DG REGIO Cohesion Open Data
-- Platform (Socrata at cohesiondata.ec.europa.eu), dataset 9qee-iv7c
-- "2021-2027 Financial Plan details by year (All CPR funds)". One row per
-- programme (cci) x financial-allocation-category x fund, with the annual
-- breakdown 2021-2027 and the total. Backs /api/v2/funding/<fund> — one
-- endpoint per fund (ERDF, ESF+, CF, JTF, Interreg, EMFAF, AMIF, BMVI, ISF;
-- EUSF / YEI / REACT-EU come from separate datasets, added later).
--
-- Refresh: full-refresh-per-fund (DELETE WHERE fund = X, then insert) by
-- backend/scripts/backfill_cohesion_finances.py. Weekly tier is appropriate
-- (DG REGIO updates programme financial plans as new versions are adopted).

CREATE TABLE IF NOT EXISTS eu_cohesion_finances (
    id                        BIGSERIAL PRIMARY KEY,
    fund                      TEXT NOT NULL,          -- ERDF, ESF, CF, JTF, INTERREG, EMFAF, AMIF, BMVI, ISF
    ms                        TEXT,                   -- Member State ISO code
    cci                       TEXT,                   -- programme CCI identifier
    cci_title                 TEXT,                   -- programme title
    dg                        TEXT,                   -- lead DG (REGIO, EMPL, HOME, MARE, ...)
    status                    TEXT,                   -- programme status (Adopted by EC, ...)
    status_date               DATE,
    ver                       TEXT,                   -- programme version
    financial_allocation_category TEXT,               -- Transition / More developed / Less developed / ...
    y2021                     NUMERIC,
    y2022                     NUMERIC,
    y2023                     NUMERIC,
    y2024                     NUMERIC,
    y2025                     NUMERIC,
    y2026                     NUMERIC,
    y2027                     NUMERIC,
    total_non_flexible_amount NUMERIC,
    total_flexible_amount     NUMERIC,
    total                     NUMERIC,                -- total EU allocation 2021-2027 for the row
    share_of_fa_in_total      NUMERIC,
    source_dataset            TEXT NOT NULL DEFAULT '9qee-iv7c',
    raw                       JSONB,                  -- full Socrata row, for completeness
    fetched_at                TIMESTAMPTZ DEFAULT NOW(),
    created_at                TIMESTAMPTZ DEFAULT NOW(),
    updated_at                TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_cohesion_finances_fund  ON eu_cohesion_finances (fund);
CREATE INDEX IF NOT EXISTS ix_cohesion_finances_ms    ON eu_cohesion_finances (ms);
CREATE INDEX IF NOT EXISTS ix_cohesion_finances_cci   ON eu_cohesion_finances (cci);

-- Supabase Data API grants (public-read table). Order: RLS -> policy -> grant.
ALTER TABLE eu_cohesion_finances ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p_cohesion_finances_read ON eu_cohesion_finances;
CREATE POLICY p_cohesion_finances_read
    ON eu_cohesion_finances FOR SELECT
    TO anon, authenticated
    USING (true);

GRANT SELECT ON eu_cohesion_finances TO anon, authenticated;
GRANT ALL    ON eu_cohesion_finances TO service_role;
GRANT USAGE, SELECT ON SEQUENCE eu_cohesion_finances_id_seq TO service_role;
