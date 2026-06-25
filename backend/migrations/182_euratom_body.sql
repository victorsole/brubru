-- Migration 182 (25 Jun 2026) -- seed the Euratom-SA body row for /api/v2/euratom. Idempotent.
INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('euratom', 'euratom', 'Euratom', 'Euratom-SA', 'Euratom Supply Agency',
  'The Euratom agency that ensures a regular and equitable supply of nuclear materials to EU users, through its co-signature of supply contracts, a market observatory and the supply of medical radioisotopes.',
  'https://euratom-supply.ec.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym, name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
