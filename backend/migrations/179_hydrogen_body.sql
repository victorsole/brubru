-- Migration 179 (25 Jun 2026) -- seed the Clean Hydrogen body row for /api/v2/hydrogen. Idempotent.
INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('hydrogen', 'hydrogen', 'Joint Undertakings', 'Clean Hydrogen', 'Clean Hydrogen Joint Undertaking',
  'The EU public-private partnership that funds research and innovation in clean hydrogen technologies across production, storage, distribution and end uses, supporting the EU hydrogen strategy and hydrogen valleys.',
  'https://www.clean-hydrogen.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym, name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
