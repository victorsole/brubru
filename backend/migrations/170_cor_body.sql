-- Migration 170 (25 Jun 2026) — seed the CoR body row for /api/v2/cor. Idempotent.
INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('cor', 'cor', 'EU bodies and advisory', 'CoR',
  'European Committee of the Regions',
  'The EU assembly of regional and local representatives: it issues opinions on EU legislative proposals with a territorial impact, gives regions and cities a voice in EU decision-making, and monitors subsidiarity, working through six thematic commissions (CIVEX, COTER, ECON, ENVE, NAT, SEDEC).',
  'https://www.cor.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym,
    name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
