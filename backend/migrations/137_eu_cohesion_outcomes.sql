-- Migration 137 — eu_cohesion_outcomes
-- Per-fund achievement / outcome indicators from the DG REGIO Cohesion Open Data
-- Platform (Socrata at cohesiondata.ec.europa.eu), dataset xi3a-zddk
-- "2021-2027 Achievement Details (multi-funds) timeseries". One row per
-- programme (cci) x indicator x category-of-region, with the baseline,
-- 2024 milestone, 2029 target, and the decided + implemented values.
--
-- The "what the money achieves" layer that complements eu_cohesion_finances
-- (the allocation layer). Backs /api/v2/funding/<fund>/outcomes — built one
-- fund at a time; ESF+ first. Only the latest TOD cycle (is_latest_tod_cycle)
-- is ingested. Full-refresh per fund. Weekly tier.

CREATE TABLE IF NOT EXISTS eu_cohesion_outcomes (
    id                          BIGSERIAL PRIMARY KEY,
    fund                        TEXT NOT NULL,        -- ESF+, ERDF, CF, JTF, ... (note: this dataset uses 'ESF+' with the plus)
    fund_family                 TEXT,
    ms                          TEXT,
    ms_name                     TEXT,
    cci                         TEXT,
    programme_short_title       TEXT,
    programme_status            TEXT,
    policy_objective_code       TEXT,
    policy_objective_name       TEXT,
    specific_objective_code     TEXT,
    specific_objective_name     TEXT,
    category_of_region          TEXT,
    indicator_type_output_result TEXT,                -- COMMON | OESF (output) | RESF (result) etc.
    common_indicators_y_n       BOOLEAN,
    ind_code                    TEXT,
    indicator_short_name        TEXT,
    indicator_long_name         TEXT,
    measurement_unit            TEXT,
    baseline_value              NUMERIC,
    milestone_value_2024        NUMERIC,
    target_value_2029           NUMERIC,
    decided_value               NUMERIC,             -- value for selected/decided operations
    implemented_value           NUMERIC,             -- value achieved by implemented operations
    tod_cycle                   TEXT,
    source_dataset              TEXT NOT NULL DEFAULT 'xi3a-zddk',
    raw                         JSONB,
    fetched_at                  TIMESTAMPTZ DEFAULT NOW(),
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_cohesion_outcomes_fund      ON eu_cohesion_outcomes (fund);
CREATE INDEX IF NOT EXISTS ix_cohesion_outcomes_ms        ON eu_cohesion_outcomes (ms);
CREATE INDEX IF NOT EXISTS ix_cohesion_outcomes_cci       ON eu_cohesion_outcomes (cci);
CREATE INDEX IF NOT EXISTS ix_cohesion_outcomes_type      ON eu_cohesion_outcomes (indicator_type_output_result);

-- Supabase Data API grants (public-read table). Order: RLS -> policy -> grant.
ALTER TABLE eu_cohesion_outcomes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p_cohesion_outcomes_read ON eu_cohesion_outcomes;
CREATE POLICY p_cohesion_outcomes_read
    ON eu_cohesion_outcomes FOR SELECT
    TO anon, authenticated
    USING (true);

GRANT SELECT ON eu_cohesion_outcomes TO anon, authenticated;
GRANT ALL    ON eu_cohesion_outcomes TO service_role;
GRANT USAGE, SELECT ON SEQUENCE eu_cohesion_outcomes_id_seq TO service_role;
