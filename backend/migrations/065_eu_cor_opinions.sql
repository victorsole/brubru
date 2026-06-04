-- 065_eu_cor_opinions.sql
-- Backing table for /api/v1/specialised/cor — every document published by the
-- European Committee of the Regions (CoR).
--
-- Source of truth (metadata): Cellar SPARQL (CELEX pattern 5{YYYY}AR{NNNN}).
-- Source of truth (extra fields not in Cellar): direct HTML scrape of
-- cor.europa.eu/en/our-work/opinions, /studies-publications, plenary pages.
--
-- Document types covered:
--   opinion                 — formal CoR opinion on a Commission proposal
--   opinion_own_initiative  — own-initiative opinion
--   resolution              — political statement
--   study                   — research output from CoR Studies & Publications
--   plenary_session         — summary of plenary decisions
--
-- CoR has 6 commissions: CIVEX (Citizenship), COTER (Cohesion Policy),
-- ECON (Economic Policy), ENVE (Environment, Climate, Energy), NAT (Natural
-- Resources), SEDEC (Social Policy, Education, Employment, Research, Culture).
--
-- Body text fetched from Cellar XHTML manifestation when present; PDF otherwise.

CREATE TABLE IF NOT EXISTS eu_cor_opinions (
    id                  BIGSERIAL PRIMARY KEY,
    celex               VARCHAR(40) UNIQUE,
    work_uri            TEXT,
    title               TEXT,
    document_date       DATE,
    adopted_date        DATE,
    document_type       VARCHAR(40),                  -- opinion / resolution / study / etc.

    resource_type_uri   TEXT,
    resource_type_label VARCHAR(100),

    -- CoR-specific structure
    commission_code     VARCHAR(8),                   -- CIVEX, COTER, ECON, ENVE, NAT, SEDEC
    rapporteur          TEXT,
    rapporteur_country  VARCHAR(2),
    rapporteur_group    VARCHAR(16),                  -- EPP/CR, PES/CR, Renew/CR, ECR/CR, ...
    session_label       TEXT,
    session_date        DATE,

    -- Vote outcome (rarely in Cellar; HTML scrape)
    vote_for            INTEGER,
    vote_against        INTEGER,
    vote_abstain        INTEGER,
    adopted             BOOLEAN,

    -- Cross-references
    related_celex       VARCHAR(40),
    related_com_ref     VARCHAR(40),
    own_initiative      BOOLEAN  NOT NULL DEFAULT false,

    -- Cellar metadata
    available_languages TEXT[]   DEFAULT ARRAY[]::TEXT[],
    eurovoc_concepts    TEXT[]   DEFAULT ARRAY[]::TEXT[],

    -- Canonical links
    eurlex_url          TEXT,
    cor_url             TEXT,

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

CREATE INDEX IF NOT EXISTS idx_eu_cor_date
    ON eu_cor_opinions (document_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_eu_cor_type
    ON eu_cor_opinions (document_type);
CREATE INDEX IF NOT EXISTS idx_eu_cor_commission
    ON eu_cor_opinions (commission_code);
CREATE INDEX IF NOT EXISTS idx_eu_cor_related_celex
    ON eu_cor_opinions (related_celex);
CREATE INDEX IF NOT EXISTS idx_eu_cor_rapporteur_country
    ON eu_cor_opinions (rapporteur_country);
CREATE INDEX IF NOT EXISTS idx_eu_cor_own_initiative
    ON eu_cor_opinions (own_initiative);
CREATE INDEX IF NOT EXISTS idx_eu_cor_title_search
    ON eu_cor_opinions USING gin (to_tsvector('english', COALESCE(title,'')));
CREATE INDEX IF NOT EXISTS idx_eu_cor_has_body
    ON eu_cor_opinions (has_body);
CREATE INDEX IF NOT EXISTS idx_eu_cor_eurovoc
    ON eu_cor_opinions USING gin (eurovoc_concepts);

-- RLS public-read (writes via service role only)
ALTER TABLE eu_cor_opinions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "eu_cor_opinions_public_read" ON eu_cor_opinions;
CREATE POLICY "eu_cor_opinions_public_read"
    ON eu_cor_opinions FOR SELECT
    USING (true);

-- Explicit Data API grants (Supabase default revoked for new tables from 30 Oct 2026).
-- Pattern A: public-read catalog. Writes only via backfill scripts using service_role.
GRANT SELECT ON eu_cor_opinions TO anon, authenticated;
GRANT ALL    ON eu_cor_opinions TO service_role;
GRANT USAGE, SELECT ON SEQUENCE eu_cor_opinions_id_seq TO service_role;

COMMENT ON TABLE eu_cor_opinions IS
    'European Committee of the Regions (CoR) opinions, resolutions, studies and '
    'plenary summaries. CELEX sector 5 type AR for opinions; HTML-scraped Drupal '
    'entries for studies and other non-Cellar doc types. 6 commissions: CIVEX, '
    'COTER, ECON, ENVE, NAT, SEDEC. Backed table for /api/v1/specialised/cor. '
    'Refresh via backfill_eu_cor.py.';
