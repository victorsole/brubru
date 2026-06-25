-- Migration 158 (25 Jun 2026) — seed the EACEA body row for the
-- /api/v2/eacea folder (api_ec.md, executive agencies). Idempotent upsert.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('eacea', 'eacea', 'Commission executive agencies', 'EACEA',
  'European Education and Culture Executive Agency',
  'The Commission executive agency that manages EU funding programmes in education, culture, audiovisual, sport, youth and citizenship: it runs Erasmus+, Creative Europe, the European Solidarity Corps, the Citizens, Equality, Rights and Values programme (CERV) and Erasmus Mundus, handling calls for proposals, grant management and scholarships.',
  'https://www.eacea.ec.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
