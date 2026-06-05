-- Migration 114 — EU general publications (API v2 "General Publications" folder)
--
-- The EU Publications Office's general publications (brochures, reports, studies)
-- — Cellar works of resource-type PUB_GEN (~6,300). Sourced via the EU SPARQL
-- endpoint (cdm ontology). Bodies composed at ingest. Public reference data.
BEGIN;
CREATE TABLE IF NOT EXISTS eu_general_publications (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    publication_id   TEXT NOT NULL UNIQUE,        -- cellar uuid
    cellar_uri       TEXT,
    title            TEXT NOT NULL,
    publication_date DATE,
    public_url       TEXT,
    body_txt         TEXT,
    body_html        TEXT,
    source_url       TEXT,
    first_seen       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetched_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_genpub_date ON eu_general_publications (publication_date DESC NULLS LAST);
ALTER TABLE eu_general_publications ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS eu_general_publications_public_read ON eu_general_publications;
CREATE POLICY eu_general_publications_public_read ON eu_general_publications
    FOR SELECT TO anon, authenticated USING (true);
GRANT SELECT ON eu_general_publications TO anon, authenticated;
GRANT ALL ON eu_general_publications TO service_role;
COMMIT;
