-- Migration 132 — 'fra' body for the EU Agency for Fundamental Rights (api_socjust.md).
INSERT INTO economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('fra', 'fra', 'Justice & interior — fundamental rights', 'FRA',
  'European Union Agency for Fundamental Rights',
  'The EU agency for fundamental rights; maintains the case-law database, Charterpedia, EFRIS and thematic rights databases, and provides evidence-based advice on fundamental rights.',
  'https://fra.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
