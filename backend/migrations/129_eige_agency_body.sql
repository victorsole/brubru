-- ---------------------------------------------------------------------------
-- Migration 129 — 'eige' body for the European Institute for Gender Equality
-- (api_socjust.md), economy_items-backed. New top-level /api/v2/eige/* domain.
-- economy_items has a FK to economy_bodies.code, so the body code must exist.
-- ON CONFLICT keeps this re-runnable.
-- ---------------------------------------------------------------------------
INSERT INTO economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('eige', 'eige', 'Justice & social — gender equality', 'EIGE',
  'European Institute for Gender Equality',
  'The EU agency for gender equality; publishes the Gender Equality Index, the Gender Statistics Database and research on gender-based violence and gender mainstreaming.',
  'https://eige.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
