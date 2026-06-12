-- ---------------------------------------------------------------------------
-- Migration 126 — 'eea' body for the European Environment Agency database
-- endpoints (environmental indicators, etc.).
--
-- New top-level /api/v2/eea/* domain (api_health.md), economy_items-backed
-- (one item_type per database). economy_items has a FK to economy_bodies.code,
-- so the body code must exist. ON CONFLICT keeps this re-runnable.
-- ---------------------------------------------------------------------------
INSERT INTO economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('eea', 'eea', 'Environment', 'EEA',
  'European Environment Agency',
  'The EU agency providing independent information on the environment; publishes the EU environmental indicators and the environmental data hub.',
  'https://www.eea.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
