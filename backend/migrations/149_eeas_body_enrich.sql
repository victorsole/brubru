-- Migration 149 (24 Jun 2026) — enrich the EEAS body row for the
-- /api/v2/eeas folder (api_eeas.md).
--
-- Migration 144 seeded a minimal EEAS row so the Move 5 framework-contract
-- scraper would not foreign-key fail. The new single-body /api/v2/eeas folder
-- also surfaces the body's mandate + website on its directory endpoint, so
-- populate them and move the row into its own folder grouping. Idempotent.
--
-- economy_bodies already exists (migration 119) with its Data API grants, so
-- this only upserts a reference row; no new table, no new GRANT.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('eeas', 'eeas', 'EU external action: the diplomatic service', 'EEAS',
  'European External Action Service',
  'The diplomatic service of the European Union: it carries out the EU''s common foreign and security policy, runs the EU delegations worldwide and supports the High Representative / Vice-President. It manages crisis response, the CSDP missions and operations, and the EU''s relations with non-EU countries and international organisations.',
  'https://www.eeas.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
