-- 064_eu_eesc_opinions.sql
-- Backing table for /api/v1/specialised/eesc — every document published by the
-- European Economic and Social Committee (EESC).
--
-- Source of truth (metadata): Cellar SPARQL (CELEX pattern 5{YYYY}AE{NNNN}).
-- Source of truth (extra fields not in Cellar): direct HTML scrape of
-- eesc.europa.eu/en/our-work/opinions-information-reports/* (Drupal SSR).
--
-- Document types covered:
--   opinion                 — formal EESC opinion on a Commission proposal
--   opinion_own_initiative  — own-initiative opinion (no underlying proposal)
--   information_report      — fact-finding paper
--   resolution              — political statement
--   position_paper          — section position
--   plenary_summary         — summary of plenary session decisions
--   exploratory_opinion     — requested by Council Presidency / EP
--
-- Body text fetched from Cellar XHTML manifestation when present; PDF otherwise
-- (no body_html in that case — we never synthesise HTML from extracted PDF text).

CREATE TABLE IF NOT EXISTS eu_eesc_opinions (
    id                  BIGSERIAL PRIMARY KEY,
    celex               VARCHAR(40) UNIQUE,
    work_uri            TEXT,
    title               TEXT,
    document_date       DATE,
    adopted_date        DATE,
    document_type       VARCHAR(40),                  -- opinion / information_report / resolution / position_paper / etc.

    resource_type_uri   TEXT,
    resource_type_label VARCHAR(100),

    -- EESC-specific structure
    section             VARCHAR(16),                  -- ECO, INT, REX, NAT, SOC, TEN, CCMI
    rapporteur          TEXT,
    co_rapporteur       TEXT,
    session_label       TEXT,                         -- e.g. "604th plenary session"
    session_date        DATE,

    -- Vote outcome (rarely in Cellar; HTML scrape)
    vote_for            INTEGER,
    vote_against        INTEGER,
    vote_abstain        INTEGER,
    adopted             BOOLEAN,

    -- Cross-references
    related_celex       VARCHAR(40),                  -- the Commission proposal this opinion responds to
    related_com_ref     VARCHAR(40),                  -- COM(YYYY) NNN reference if known
    own_initiative      BOOLEAN  NOT NULL DEFAULT false,

    -- Cellar metadata
    available_languages TEXT[]   DEFAULT ARRAY[]::TEXT[],
    eurovoc_concepts    TEXT[]   DEFAULT ARRAY[]::TEXT[],

    -- Canonical links
    eurlex_url          TEXT,
    eesc_url            TEXT,                         -- the eesc.europa.eu landing page if found

    -- Body fields per Brubru v1 contract
    has_body            BOOLEAN  NOT NULL DEFAULT false,
    body_html           TEXT,
    body_text           TEXT,
    body_source         VARCHAR(8),                   -- cellar_xhtml / cellar_pdf / scrape

    -- Brubru-managed timestamps
    fetched_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eu_eesc_date
    ON eu_eesc_opinions (document_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_eu_eesc_type
    ON eu_eesc_opinions (document_type);
CREATE INDEX IF NOT EXISTS idx_eu_eesc_section
    ON eu_eesc_opinions (section);
CREATE INDEX IF NOT EXISTS idx_eu_eesc_related_celex
    ON eu_eesc_opinions (related_celex);
CREATE INDEX IF NOT EXISTS idx_eu_eesc_own_initiative
    ON eu_eesc_opinions (own_initiative);
CREATE INDEX IF NOT EXISTS idx_eu_eesc_title_search
    ON eu_eesc_opinions USING gin (to_tsvector('english', COALESCE(title,'')));
CREATE INDEX IF NOT EXISTS idx_eu_eesc_has_body
    ON eu_eesc_opinions (has_body);
CREATE INDEX IF NOT EXISTS idx_eu_eesc_eurovoc
    ON eu_eesc_opinions USING gin (eurovoc_concepts);

-- RLS public-read (writes via service role only)
ALTER TABLE eu_eesc_opinions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "eu_eesc_opinions_public_read" ON eu_eesc_opinions;
CREATE POLICY "eu_eesc_opinions_public_read"
    ON eu_eesc_opinions FOR SELECT
    USING (true);

-- Explicit Data API grants (Supabase default revoked for new tables from 30 Oct 2026).
-- Pattern A: public-read catalog. Writes only via backfill scripts using service_role.
GRANT SELECT ON eu_eesc_opinions TO anon, authenticated;
GRANT ALL    ON eu_eesc_opinions TO service_role;
GRANT USAGE, SELECT ON SEQUENCE eu_eesc_opinions_id_seq TO service_role;

COMMENT ON TABLE eu_eesc_opinions IS
    'European Economic and Social Committee (EESC) opinions, information reports, '
    'resolutions, position papers and plenary summaries. CELEX sector 5 type AE for '
    'opinions; HTML-scraped Drupal entries for non-Cellar doc types. Backed table '
    'for /api/v1/specialised/eesc. Refresh via backfill_eu_eesc.py.';
