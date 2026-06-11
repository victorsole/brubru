-- ---------------------------------------------------------------------------
-- Migration 124 — shared 'parliament' body for the European Parliament
-- database endpoints (MEP declarations of financial interests, accredited
-- parliamentary assistants register, committee supporting-analyses studies).
--
-- These live as new economy_items-backed resources surfaced under the
-- /api/v2/parliament/* domain (one item_type per database). economy_items has
-- a FK to economy_bodies.code, so the shared body code must exist.
-- ON CONFLICT keeps this re-runnable.
-- ---------------------------------------------------------------------------
INSERT INTO economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('parliament', 'parliament', 'European Parliament', 'EP',
  'European Parliament',
  'Directly elected legislature of the European Union; the Parliament databases (MEP declarations of financial interests, accredited assistants, committee supporting analyses, etc.).',
  'https://www.europarl.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
