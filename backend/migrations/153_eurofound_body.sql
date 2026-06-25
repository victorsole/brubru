-- Migration 153 (25 Jun 2026) — seed the Eurofound body row for the
-- /api/v2/eurofound folder (api_socjust.md). Idempotent upsert.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('eurofound', 'eurofound', 'Employment and social affairs: living and working conditions', 'Eurofound',
  'European Foundation for the Improvement of Living and Working Conditions',
  'The EU agency for living and working conditions: it runs Europe-wide surveys (working conditions, quality of life, companies), monitors restructuring and convergence, and provides comparative analysis on employment, social policy and industrial relations to support EU policymaking.',
  'https://www.eurofound.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
