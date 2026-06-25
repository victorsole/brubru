-- Migration 159 (25 Jun 2026) — seed the HaDEA body row for the
-- /api/v2/hadea folder (api_ec.md, executive agencies). Idempotent upsert.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('hadea', 'hadea', 'Commission executive agencies', 'HaDEA',
  'European Health and Digital Executive Agency',
  'The Commission executive agency that manages EU funding programmes in health and digital: it runs EU4Health, the Single Market Programme (food safety strand), Horizon Europe health and digital clusters, the Connecting Europe Facility (digital) and the Digital Europe Programme, handling calls for proposals, calls for tenders and grant management.',
  'https://hadea.ec.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
