-- 057_eu_trade_defence_measures.sql
-- Backing table for /api/v1/specialised/trade-defence — every EU
-- anti-dumping / countervailing / safeguard regulation in Cellar.
-- One row per CELEX. Sourced from Cellar sector-3 type-R regulations
-- whose title matches the trade-defence keyword set.

CREATE TABLE IF NOT EXISTS eu_trade_defence_measures (
    id                  BIGSERIAL PRIMARY KEY,
    celex               VARCHAR(40) NOT NULL UNIQUE,
    work_uri            TEXT,
    title               TEXT,
    document_date       DATE,

    -- Brubru-derived classification (regex on title)
    measure_type        VARCHAR(40),   -- 'anti_dumping','countervailing','safeguard','suspension','amendment','termination','registration','review'
    duty_status         VARCHAR(20),   -- 'definitive','provisional','initiation','registration','review','expiry','termination','interim'
    target_country      TEXT,
    product             TEXT,

    -- Cellar metadata
    resource_type_uri   TEXT,
    resource_type_label VARCHAR(100),
    in_force            BOOLEAN,
    date_in_force       DATE,
    date_end_validity   DATE,
    available_languages TEXT[]   DEFAULT ARRAY[]::TEXT[],
    eurovoc_concepts    TEXT[]   DEFAULT ARRAY[]::TEXT[],

    eurlex_url          TEXT NOT NULL,

    -- v1 body contract
    has_body            BOOLEAN  NOT NULL DEFAULT false,
    body_html           TEXT,
    body_text           TEXT,
    body_source         VARCHAR(8),

    fetched_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_etdm_date ON eu_trade_defence_measures (document_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_etdm_in_force ON eu_trade_defence_measures (in_force);
CREATE INDEX IF NOT EXISTS idx_etdm_measure_type ON eu_trade_defence_measures (measure_type);
CREATE INDEX IF NOT EXISTS idx_etdm_duty_status ON eu_trade_defence_measures (duty_status);
CREATE INDEX IF NOT EXISTS idx_etdm_target_country ON eu_trade_defence_measures (target_country);
CREATE INDEX IF NOT EXISTS idx_etdm_product ON eu_trade_defence_measures (product);
CREATE INDEX IF NOT EXISTS idx_etdm_title_search
    ON eu_trade_defence_measures USING gin (to_tsvector('english', COALESCE(title,'')));

ALTER TABLE eu_trade_defence_measures ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "etdm_public_read" ON eu_trade_defence_measures;
CREATE POLICY "etdm_public_read" ON eu_trade_defence_measures FOR SELECT USING (true);

COMMENT ON TABLE eu_trade_defence_measures IS
    'EU trade-defence regulations (anti-dumping, countervailing, safeguard) '
    'from Cellar sector-3 type-R. Backing table for /api/v1/specialised/trade-defence.';
