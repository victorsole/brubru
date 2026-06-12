-- ---------------------------------------------------------------------------
-- Migration 127 — 'echa' body for the European Chemicals Agency database
-- endpoints (REACH Candidate List of SVHC, etc.).
--
-- New top-level /api/v2/echa/* domain (api_health.md), economy_items-backed
-- (one item_type per database). economy_items has a FK to economy_bodies.code,
-- so the body code must exist. ON CONFLICT keeps this re-runnable.
-- ---------------------------------------------------------------------------
INSERT INTO economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('echa', 'echa', 'Chemicals', 'ECHA',
  'European Chemicals Agency',
  'The EU agency implementing the REACH, CLP, Biocides and POPs chemicals legislation; publishes the Candidate List of substances of very high concern and the registered-substances database.',
  'https://echa.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
