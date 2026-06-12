-- Migration 131 — 'euaa' body for the EU Agency for Asylum (api_socjust.md).
INSERT INTO economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('euaa', 'euaa', 'Justice & interior — asylum', 'EUAA',
  'European Union Agency for Asylum',
  'The EU agency for asylum; publishes Country of Origin Information, country guidance, the Asylum Report and asylum case-law analysis, and supports member states on asylum and reception.',
  'https://www.euaa.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
