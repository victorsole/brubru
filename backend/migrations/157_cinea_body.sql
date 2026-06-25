-- Migration 157 (25 Jun 2026) — seed the CINEA body row for the
-- /api/v2/cinea folder (api_ec.md, executive agencies). Idempotent upsert.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('cinea', 'cinea', 'Commission executive agencies', 'CINEA',
  'European Climate, Infrastructure and Environment Executive Agency',
  'The Commission executive agency that manages EU funding programmes for climate, energy, transport, environment and the blue economy: it runs the Connecting Europe Facility (energy and transport), Horizon Europe energy, the LIFE programme, the Innovation and Modernisation Funds, the Renewable Energy Financing Mechanism and the Green Assist advisory service.',
  'https://cinea.ec.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
