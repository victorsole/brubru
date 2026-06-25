-- Migration 181 (25 Jun 2026) -- seed the EuroHPC body row for /api/v2/eurohpc. Idempotent.
INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('eurohpc', 'eurohpc', 'Joint Undertakings', 'EuroHPC', 'European High Performance Computing Joint Undertaking',
  'The EU body that procures and operates world-class supercomputers, AI factories and quantum computers and funds HPC research, pooling EU and national resources to build Europes supercomputing capacity.',
  'https://www.eurohpc-ju.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym, name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
