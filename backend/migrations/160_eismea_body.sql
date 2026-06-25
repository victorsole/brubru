-- Migration 160 (25 Jun 2026) — seed the EISMEA body row for the
-- /api/v2/eismea folder (api_ec.md, executive agencies). Idempotent upsert.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('eismea', 'eismea', 'Commission executive agencies', 'EISMEA',
  'European Innovation Council and SMEs Executive Agency',
  'The Commission executive agency that manages EU programmes for innovation and small and medium-sized enterprises: it runs the European Innovation Council, the European Innovation Ecosystems, the Single Market Programme and the Interregional Innovation Investments (I3) instrument, handling calls for proposals and grant management.',
  'https://eismea.ec.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
