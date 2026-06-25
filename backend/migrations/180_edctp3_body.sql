-- Migration 180 (25 Jun 2026) -- seed the EDCTP3 body row for /api/v2/edctp3. Idempotent.
INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('edctp3', 'edctp3', 'Joint Undertakings', 'EDCTP3', 'Global Health EDCTP3 Joint Undertaking',
  'The EU-Africa partnership that funds clinical research to develop new and improved medical interventions against infectious diseases in sub-Saharan Africa and strengthens research capacity.',
  'https://www.global-health-edctp3.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym, name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
