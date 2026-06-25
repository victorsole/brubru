-- Migration 169 (25 Jun 2026) — seed the EESC body row for /api/v2/eesc. Idempotent.
INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('eesc', 'eesc', 'EU bodies and advisory', 'EESC',
  'European Economic and Social Committee',
  'The EU consultative body representing employers, workers and civil-society organisations: it issues opinions on EU legislative proposals and own-initiative reports, bringing organised civil society into the EU decision-making process across all policy areas.',
  'https://www.eesc.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym,
    name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
