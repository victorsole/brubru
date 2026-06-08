-- Migration 119 — Economy & Finance institutions (API v2)
--
-- Shared data layer for the three new v2 economy/finance folders:
--   /api/v2/ecb                      — ECB + ECB Banking Supervision (SSM)
--   /api/v2/eu-financial-institutions — EBA, ESMA, EIOPA, ESRB, SRB, EIB, AMLA, EPPO
--   /api/v2/esm                      — European Stability Mechanism
--
-- The folder split is purely code/URL organisation; the data layer is unified so
-- "backfill all" is one mechanism across every body.
--
--   economy_bodies — one reference row per institution/body (11 total).
--   economy_items  — dated documents per body, item_type ∈ news|publication|event|legal,
--                    each carrying the 5 mandatory datapoints
--                    (public_url, body_txt, body_html, document_date, creation_date).
--
-- Public reference data: anon + authenticated SELECT, service_role ALL. Re-runnable.

BEGIN;

CREATE TABLE IF NOT EXISTS economy_bodies (
    code               VARCHAR(40) PRIMARY KEY,   -- 'ecb', 'ecb_ssm', 'eba', ...
    folder             VARCHAR(40) NOT NULL,       -- 'ecb' | 'eu_financial_institutions' | 'esm'
    family             TEXT NOT NULL,              -- the doc's "#" family label
    acronym            VARCHAR(20) NOT NULL,
    name               TEXT NOT NULL,
    mandate            TEXT,
    website            TEXT,
    is_eu_institution  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS economy_items (
    id             BIGSERIAL PRIMARY KEY,
    body_code      VARCHAR(40) NOT NULL REFERENCES economy_bodies (code) ON DELETE CASCADE,
    item_type      VARCHAR(20) NOT NULL,           -- news | publication | event | legal
    title          TEXT NOT NULL,
    summary        TEXT,

    -- 5 mandatory datapoints (v1/v2 contract)
    public_url     TEXT NOT NULL,
    body_txt       TEXT,
    body_html      TEXT,
    document_date  TIMESTAMPTZ,                    -- the item's own published date
    creation_date  TIMESTAMPTZ,                    -- when Brubru first ingested it

    -- provenance
    source_kind    VARCHAR(20),                    -- rss | html | pdf | cellar
    guid           TEXT,                           -- rss guid / canonical url (dedup aid)
    fetched_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (body_code, item_type, public_url)
);

CREATE INDEX IF NOT EXISTS economy_items_body_type_date
    ON economy_items (body_code, item_type, document_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS economy_items_type_date
    ON economy_items (item_type, document_date DESC NULLS LAST);

-- ---------------------------------------------------------------------------
-- Seed the 11 bodies (reference data). ON CONFLICT keeps this re-runnable.
-- ---------------------------------------------------------------------------
INSERT INTO economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('ecb',     'ecb', 'European Central Bank', 'ECB',
   'European Central Bank', 'Monetary policy and the euro for the euro area.', 'https://www.ecb.europa.eu', TRUE),
 ('ecb_ssm', 'ecb', 'European Central Bank', 'SSM',
   'ECB Banking Supervision', 'Single Supervisory Mechanism — prudential supervision of euro-area banks.', 'https://www.bankingsupervision.europa.eu', TRUE),

 ('eba',   'eu_financial_institutions', 'European System of Financial Supervision', 'EBA',
   'European Banking Authority', 'Single rulebook and supervisory convergence for EU banking.', 'https://www.eba.europa.eu', TRUE),
 ('esma',  'eu_financial_institutions', 'European System of Financial Supervision', 'ESMA',
   'European Securities and Markets Authority', 'EU securities markets regulator and supervisor.', 'https://www.esma.europa.eu', TRUE),
 ('eiopa', 'eu_financial_institutions', 'European System of Financial Supervision', 'EIOPA',
   'European Insurance and Occupational Pensions Authority', 'EU insurance and occupational pensions authority.', 'https://www.eiopa.europa.eu', TRUE),
 ('esrb',  'eu_financial_institutions', 'European System of Financial Supervision', 'ESRB',
   'European Systemic Risk Board', 'Macroprudential oversight of the EU financial system.', 'https://www.esrb.europa.eu', TRUE),
 ('srb',   'eu_financial_institutions', 'Banking Union', 'SRB',
   'Single Resolution Board', 'Central resolution authority of the Banking Union.', 'https://www.srb.europa.eu', TRUE),
 ('eib',   'eu_financial_institutions', 'EIB Group & financial instruments', 'EIB',
   'European Investment Bank', 'The EU''s lending arm (EIB Group, including the European Investment Fund).', 'https://www.eib.org', TRUE),
 ('amla',  'eu_financial_institutions', 'Anti-money-laundering, anti-fraud & financial crime', 'AMLA',
   'Anti-Money Laundering Authority', 'EU anti-money-laundering and countering-terrorist-financing supervisor.', 'https://www.amla.europa.eu', TRUE),
 ('eppo',  'eu_financial_institutions', 'Anti-money-laundering, anti-fraud & financial crime', 'EPPO',
   'European Public Prosecutor''s Office', 'Independent EU body prosecuting crimes against the EU budget.', 'https://www.eppo.europa.eu', TRUE),

 ('esm',   'esm', 'Intergovernmental (linked, not EU institutions)', 'ESM',
   'European Stability Mechanism', 'Euro-area firewall providing financial assistance (intergovernmental, not an EU institution).', 'https://www.esm.europa.eu', FALSE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;

-- ---------------------------------------------------------------------------
-- RLS + grants (Supabase Data API mandate)
-- ---------------------------------------------------------------------------
ALTER TABLE economy_bodies ENABLE ROW LEVEL SECURITY;
ALTER TABLE economy_items  ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS economy_bodies_public_read ON economy_bodies;
CREATE POLICY economy_bodies_public_read ON economy_bodies
    FOR SELECT TO anon, authenticated USING (true);
DROP POLICY IF EXISTS economy_items_public_read ON economy_items;
CREATE POLICY economy_items_public_read ON economy_items
    FOR SELECT TO anon, authenticated USING (true);

GRANT SELECT ON economy_bodies TO anon, authenticated;
GRANT ALL    ON economy_bodies TO service_role;
GRANT SELECT ON economy_items  TO anon, authenticated;
GRANT ALL    ON economy_items  TO service_role;
GRANT USAGE, SELECT ON SEQUENCE economy_items_id_seq TO service_role;

COMMIT;
