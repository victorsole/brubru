-- Migration 152 (25 Jun 2026) — seed the ELA body row for the /api/v2/ela
-- folder (api_socjust.md). Idempotent upsert; economy_bodies already exists.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('ela', 'ela', 'Employment and social affairs: labour mobility', 'ELA',
  'European Labour Authority',
  'The EU agency for labour mobility: it helps the member states and the Commission apply EU rules on labour mobility and the coordination of social security, supports EURES, and coordinates concerted and joint inspections.',
  'https://www.ela.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
