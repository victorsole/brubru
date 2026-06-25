-- Migration 163 (25 Jun 2026) — seed the EPSO body row for the
-- /api/v2/epso folder (api_ec.md). Idempotent upsert.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('epso', 'epso', 'Interinstitutional services', 'EPSO',
  'European Personnel Selection Office',
  'The interinstitutional office that organises open competitions and selection procedures to recruit permanent and contract staff for the EU institutions, bodies and agencies: it runs the EU Careers competitions, the CAST permanent selection for contract agents, traineeships and the candidate testing and reserve-list process.',
  'https://eu-careers.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
