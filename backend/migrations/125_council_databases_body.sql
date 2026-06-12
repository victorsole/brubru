-- ---------------------------------------------------------------------------
-- Migration 125 — shared 'council' body for the Council of the EU database
-- endpoints (EU sanctions / restrictive measures regimes, etc.).
--
-- These live as new economy_items-backed resources surfaced under the
-- /api/v2/council/* domain (one item_type per database), alongside the existing
-- council_register_items-backed endpoints. economy_items has a FK to
-- economy_bodies.code, so the shared body code must exist.
-- ON CONFLICT keeps this re-runnable.
-- ---------------------------------------------------------------------------
INSERT INTO economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('council', 'council', 'Council of the EU', 'Council',
  'Council of the European Union',
  'The institution representing EU member-state governments; adopts EU law jointly with the Parliament and decides on the EU restrictive measures (sanctions) regimes.',
  'https://www.consilium.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
