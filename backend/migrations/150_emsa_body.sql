-- Migration 150 (25 Jun 2026) — seed the EMSA body row for the /api/v2/emsa
-- folder (api_socjust.md). economy_bodies already exists (migration 119) with
-- its Data API grants, so this only upserts one reference row. Idempotent.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('emsa', 'emsa', 'Transport: maritime safety', 'EMSA',
  'European Maritime Safety Agency',
  'The EU agency for maritime safety: it supports the Commission and the member states on ship safety, the prevention of pollution by ships, maritime surveillance and the digitalisation of shipping.',
  'https://www.emsa.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
