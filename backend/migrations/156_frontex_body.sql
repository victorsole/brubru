-- Migration 156 (25 Jun 2026) — seed the Frontex body row for the
-- /api/v2/frontex folder (api_socjust.md). Idempotent upsert.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('frontex', 'frontex', 'Justice and home affairs: border management', 'Frontex',
  'European Border and Coast Guard Agency',
  'The EU agency that supports Member States and Schengen-associated countries in managing the external borders and fighting cross-border crime: it deploys a standing corps of border and coast guards, coordinates joint operations and returns, runs risk analysis and situational monitoring, and supports search-and-rescue at the external borders.',
  'https://www.frontex.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
