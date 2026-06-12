-- ---------------------------------------------------------------------------
-- Migration 128 — 'euda' body for the European Union Drugs Agency database
-- endpoints (publications library, etc.).
--
-- New top-level /api/v2/euda/* domain (api_health.md, formerly EMCDDA),
-- economy_items-backed (one item_type per database). economy_items has a FK to
-- economy_bodies.code, so the body code must exist. ON CONFLICT keeps this
-- re-runnable.
-- ---------------------------------------------------------------------------
INSERT INTO economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('euda', 'euda', 'Health — drugs', 'EUDA',
  'European Union Drugs Agency',
  'The EU agency for the drugs phenomenon (formerly EMCDDA); publishes the European Drug Report, EU Drug Markets analyses and the drugs reference library.',
  'https://www.euda.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
