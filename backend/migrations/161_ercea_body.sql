-- Migration 161 (25 Jun 2026) — seed the ERCEA body row for the
-- /api/v2/ercea folder (api_ec.md, executive agencies). Idempotent upsert.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('ercea', 'ercea', 'Commission executive agencies', 'ERCEA',
  'European Research Council Executive Agency',
  'The Commission executive agency that implements the European Research Council: it manages the ERC frontier-research grant scheme (Starting, Consolidator, Advanced, Proof of Concept and Synergy grants), runs the evaluation and award process and supports the ERC Scientific Council.',
  'https://erc.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
