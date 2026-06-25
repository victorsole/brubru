-- Migration 151 (25 Jun 2026) — seed the EUSPA body row for the /api/v2/euspa
-- folder (api_socjust.md). Idempotent upsert; economy_bodies already exists.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('euspa', 'euspa', 'Single market: the space programme', 'EUSPA',
  'European Union Agency for the Space Programme',
  'The EU agency for the space programme: it operates Galileo and EGNOS, supports Copernicus, secure connectivity and space situational awareness, and grows the EU space market and user uptake.',
  'https://www.euspa.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
