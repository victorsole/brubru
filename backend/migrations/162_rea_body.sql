-- Migration 162 (25 Jun 2026) — seed the REA body row for the
-- /api/v2/rea folder (api_ec.md, executive agencies). Idempotent upsert.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('rea', 'rea', 'Commission executive agencies', 'REA',
  'European Research Executive Agency',
  'The Commission executive agency that implements parts of Horizon Europe: it manages grants under cluster 2 (culture, creativity and inclusive society) and cluster 3 (civil security for society), the EU Soil Mission, Marie Sklodowska-Curie Actions support and the agricultural products promotion programme, handling calls, evaluation and grant management.',
  'https://rea.ec.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
