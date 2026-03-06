-- Migration 030: Add DG GROW database tables
-- NANDO (notified bodies), TRIS (technical regulations), TBT (trade barriers), EMI (industrial ecosystems)
-- Source: https://single-market-economy.ec.europa.eu/tools-databases_en

-- 1. Notified Bodies (NANDO / Single Market Compliance Space)
CREATE TABLE IF NOT EXISTS notified_bodies (
    id SERIAL PRIMARY KEY,
    nando_id VARCHAR(20) UNIQUE NOT NULL,
    body_name VARCHAR(500) NOT NULL,
    body_number VARCHAR(10),
    country VARCHAR(2) NOT NULL,
    address TEXT,
    city VARCHAR(200),
    postal_code VARCHAR(20),
    phone VARCHAR(100),
    email VARCHAR(300),
    website VARCHAR(500),
    directives TEXT[],
    directive_names TEXT[],
    regulations TEXT[],
    product_areas TEXT[],
    cpv_mapping VARCHAR(20)[],
    status VARCHAR(20) DEFAULT 'active',
    notification_date TIMESTAMPTZ,
    expiry_date TIMESTAMPTZ,
    source_url VARCHAR(500),
    raw_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notified_bodies_nando_id ON notified_bodies(nando_id);
CREATE INDEX IF NOT EXISTS idx_notified_bodies_country ON notified_bodies(country);
CREATE INDEX IF NOT EXISTS idx_notified_bodies_body_number ON notified_bodies(body_number);
CREATE INDEX IF NOT EXISTS idx_notified_bodies_status ON notified_bodies(status);
CREATE INDEX IF NOT EXISTS idx_notified_bodies_country_status ON notified_bodies(country, status);
CREATE INDEX IF NOT EXISTS idx_notified_bodies_directives ON notified_bodies USING GIN(directives);
CREATE INDEX IF NOT EXISTS idx_notified_bodies_cpv ON notified_bodies USING GIN(cpv_mapping);

-- 2. Technical Regulations (TRIS)
CREATE TABLE IF NOT EXISTS technical_regulations (
    id SERIAL PRIMARY KEY,
    notification_number INTEGER UNIQUE NOT NULL,
    reference VARCHAR(50),
    title TEXT NOT NULL,
    description TEXT,
    product_sector VARCHAR(200),
    product_description TEXT,
    country VARCHAR(2) NOT NULL,
    country_name VARCHAR(100),
    notification_date TIMESTAMPTZ NOT NULL,
    standstill_end_date TIMESTAMPTZ,
    adoption_date TIMESTAMPTZ,
    status VARCHAR(30) DEFAULT 'notified',
    has_detailed_opinion BOOLEAN DEFAULT FALSE,
    has_comments BOOLEAN DEFAULT FALSE,
    related_eu_legislation TEXT[],
    related_directives TEXT[],
    cpv_mapping VARCHAR(20)[],
    source_url VARCHAR(500),
    document_url VARCHAR(500),
    raw_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tech_regs_number ON technical_regulations(notification_number);
CREATE INDEX IF NOT EXISTS idx_tech_regs_country ON technical_regulations(country);
CREATE INDEX IF NOT EXISTS idx_tech_regs_date ON technical_regulations(notification_date DESC);
CREATE INDEX IF NOT EXISTS idx_tech_regs_sector ON technical_regulations(product_sector);
CREATE INDEX IF NOT EXISTS idx_tech_regs_status ON technical_regulations(status);
CREATE INDEX IF NOT EXISTS idx_tech_regs_country_date ON technical_regulations(country, notification_date DESC);
CREATE INDEX IF NOT EXISTS idx_tech_regs_cpv ON technical_regulations USING GIN(cpv_mapping);

-- 3. Trade Barrier Notifications (TBT)
CREATE TABLE IF NOT EXISTS trade_barrier_notifications (
    id SERIAL PRIMARY KEY,
    notification_id INTEGER UNIQUE NOT NULL,
    symbol VARCHAR(100),
    title TEXT NOT NULL,
    description TEXT,
    product_description TEXT,
    objective TEXT,
    country VARCHAR(100) NOT NULL,
    country_code VARCHAR(3),
    hs_codes VARCHAR(20)[],
    ics_codes VARCHAR(20)[],
    product_area VARCHAR(200),
    notification_date TIMESTAMPTZ NOT NULL,
    comment_deadline TIMESTAMPTZ,
    proposed_adoption_date TIMESTAMPTZ,
    proposed_entry_into_force TIMESTAMPTZ,
    status VARCHAR(30) DEFAULT 'notified',
    is_eu_notification BOOLEAN DEFAULT FALSE,
    has_eu_comment BOOLEAN DEFAULT FALSE,
    trade_impact VARCHAR(50),
    affected_eu_sectors TEXT[],
    cpv_mapping VARCHAR(20)[],
    source_url VARCHAR(500),
    raw_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tbt_notification_id ON trade_barrier_notifications(notification_id);
CREATE INDEX IF NOT EXISTS idx_tbt_country ON trade_barrier_notifications(country);
CREATE INDEX IF NOT EXISTS idx_tbt_date ON trade_barrier_notifications(notification_date DESC);
CREATE INDEX IF NOT EXISTS idx_tbt_eu ON trade_barrier_notifications(is_eu_notification);
CREATE INDEX IF NOT EXISTS idx_tbt_status ON trade_barrier_notifications(status);
CREATE INDEX IF NOT EXISTS idx_tbt_product_area ON trade_barrier_notifications(product_area);
CREATE INDEX IF NOT EXISTS idx_tbt_cpv ON trade_barrier_notifications USING GIN(cpv_mapping);

-- 4. Industrial Ecosystem Data (EMI)
CREATE TABLE IF NOT EXISTS industrial_ecosystem_data (
    id SERIAL PRIMARY KEY,
    ecosystem VARCHAR(100) NOT NULL,
    country VARCHAR(2),
    indicator VARCHAR(200) NOT NULL,
    period VARCHAR(20) NOT NULL,
    value FLOAT,
    unit VARCHAR(50),
    previous_value FLOAT,
    change_pct FLOAT,
    dimension VARCHAR(50),
    sub_dimension VARCHAR(100),
    cpv_categories VARCHAR(20)[],
    source_report VARCHAR(300),
    source_url VARCHAR(500),
    raw_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(ecosystem, country, indicator, period)
);

CREATE INDEX IF NOT EXISTS idx_emi_ecosystem ON industrial_ecosystem_data(ecosystem);
CREATE INDEX IF NOT EXISTS idx_emi_country ON industrial_ecosystem_data(country);
CREATE INDEX IF NOT EXISTS idx_emi_indicator ON industrial_ecosystem_data(indicator);
CREATE INDEX IF NOT EXISTS idx_emi_period ON industrial_ecosystem_data(period);
CREATE INDEX IF NOT EXISTS idx_emi_dimension ON industrial_ecosystem_data(dimension);
CREATE INDEX IF NOT EXISTS idx_emi_ecosystem_indicator ON industrial_ecosystem_data(ecosystem, indicator);
CREATE INDEX IF NOT EXISTS idx_emi_cpv ON industrial_ecosystem_data USING GIN(cpv_categories);
