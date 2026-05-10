-- 056_eu_trade_agreements.sql
-- Backing table for /api/v1/specialised/fta — every international agreement
-- signed by the EU (CELEX sector 2, type letter A). Covers FTAs, EPAs,
-- Association Agreements, PCAs, Fisheries Partnership Agreements, Aviation
-- Agreements, tax-info exchanges, and the Exchange-of-Letters family.
--
-- Source of truth: Cellar SPARQL (sector="2", type="A"). Body text fetched
-- from Cellar XHTML manifestation when present; PDF otherwise (no body_html
-- in that case — we never synthesise HTML from extracted PDF text).

CREATE TABLE IF NOT EXISTS eu_trade_agreements (
    id                  BIGSERIAL PRIMARY KEY,
    celex               VARCHAR(40) NOT NULL UNIQUE,
    work_uri            TEXT,
    title               TEXT,
    document_date       DATE,

    resource_type_uri   TEXT,
    resource_type_label VARCHAR(100),

    -- Brubru-derived classification, best-effort from title regex
    agreement_type      VARCHAR(40),
    partner             TEXT,

    -- Cellar metadata
    in_force            BOOLEAN,
    date_in_force       DATE,
    date_end_validity   DATE,
    available_languages TEXT[]   DEFAULT ARRAY[]::TEXT[],
    eurovoc_concepts    TEXT[]   DEFAULT ARRAY[]::TEXT[],

    -- Canonical link
    eurlex_url          TEXT NOT NULL,

    -- Body fields per Brubru v1 contract
    has_body            BOOLEAN  NOT NULL DEFAULT false,
    body_html           TEXT,
    body_text           TEXT,
    body_source         VARCHAR(8),

    -- Brubru-managed timestamps
    fetched_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eu_trade_agreements_date
    ON eu_trade_agreements (document_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_eu_trade_agreements_in_force
    ON eu_trade_agreements (in_force);
CREATE INDEX IF NOT EXISTS idx_eu_trade_agreements_type
    ON eu_trade_agreements (agreement_type);
CREATE INDEX IF NOT EXISTS idx_eu_trade_agreements_partner
    ON eu_trade_agreements (partner);
CREATE INDEX IF NOT EXISTS idx_eu_trade_agreements_title_search
    ON eu_trade_agreements USING gin (to_tsvector('english', COALESCE(title,'')));
CREATE INDEX IF NOT EXISTS idx_eu_trade_agreements_has_body
    ON eu_trade_agreements (has_body);

-- RLS public-read (writes via service role only)
ALTER TABLE eu_trade_agreements ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "eu_trade_agreements_public_read" ON eu_trade_agreements;
CREATE POLICY "eu_trade_agreements_public_read"
    ON eu_trade_agreements FOR SELECT
    USING (true);

COMMENT ON TABLE eu_trade_agreements IS
    'EU international agreements (CELEX sector 2, type A). Includes FTAs, EPAs, '
    'Association Agreements, PCAs, Fisheries Partnership Agreements, Aviation, '
    'tax-info exchanges and Exchange-of-Letters instruments. Backed table for '
    '/api/v1/specialised/fta. Refresh by re-running backfill_eu_trade_agreements.py.';
