-- Migration 154 (25 Jun 2026) — seed the CEPOL body row for the
-- /api/v2/cepol folder (api_socjust.md). Idempotent upsert.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('cepol', 'cepol', 'Justice and home affairs: police cooperation', 'CEPOL',
  'European Union Agency for Law Enforcement Training',
  'The EU agency that develops, delivers and coordinates training for law enforcement officials across Member States and partner countries: it runs residential and online courses, an exchange programme and a research and science conference, covering counter-terrorism, cybercrime, serious and organised crime, fundamental rights and leadership.',
  'https://www.cepol.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
