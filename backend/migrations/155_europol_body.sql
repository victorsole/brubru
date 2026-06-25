-- Migration 155 (25 Jun 2026) — seed the Europol body row for the
-- /api/v2/europol folder (api_socjust.md). Idempotent upsert.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('europol', 'europol', 'Justice and home affairs: police cooperation', 'Europol',
  'European Union Agency for Law Enforcement Cooperation',
  'The EU agency that supports Member States in preventing and combating serious international and organised crime, cybercrime and terrorism: it runs operational and analysis centres, hosts specialist hubs (ESOCC, EC3, ECTC, EFECC), coordinates cross-border operations and publishes flagship threat assessments such as SOCTA and IOCTA.',
  'https://www.europol.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
