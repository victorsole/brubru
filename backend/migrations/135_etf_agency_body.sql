-- Migration 135 — 'etf' body for the European Training Foundation procurement.
INSERT INTO economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('etf', 'etf', 'Justice & social — training', 'ETF',
  'European Training Foundation',
  'The EU agency supporting human-capital development in partner countries; runs its own procurement and calls.',
  'https://www.etf.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
