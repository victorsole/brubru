-- ---------------------------------------------------------------------------
-- Migration 130 — 'cedefop' body for the European Centre for the Development of
-- Vocational Training (api_socjust.md), economy_items-backed. New top-level
-- /api/v2/cedefop/* domain. ON CONFLICT keeps this re-runnable.
-- ---------------------------------------------------------------------------
INSERT INTO economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('cedefop', 'cedefop', 'Justice & social — skills', 'Cedefop',
  'European Centre for the Development of Vocational Training',
  'The EU agency for vocational education and training and skills; publishes the European Skills Index, Skills-OVATE, the Skills Forecast and VET policy analysis.',
  'https://www.cedefop.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
