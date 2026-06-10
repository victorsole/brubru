-- ---------------------------------------------------------------------------
-- Migration 123 — shared 'commission' body for the European Commission
-- database endpoints (financial sanctions, EU funding recipients, CORDIS
-- research projects, tariff rulings, TARIC, and the tier-2 case registers).
--
-- These live as new folders under /api/v2/commission/* and reuse the
-- economy_items store (one item_type + sub-folder per database). economy_items
-- has a FK to economy_bodies.code, so the shared body code must exist.
-- ON CONFLICT keeps this re-runnable.
-- ---------------------------------------------------------------------------
INSERT INTO economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('commission', 'commission', 'European Commission', 'EC',
  'European Commission',
  'Executive of the European Union; the Commission databases (sanctions, funding, research, customs, competition, etc.).',
  'https://commission.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
