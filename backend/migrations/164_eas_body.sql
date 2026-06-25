-- Migration 164 (25 Jun 2026) — seed the European School of Administration (EAS/EUSA)
-- body row for the /api/v2/eas folder (api_ec.md). Idempotent upsert.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('eas', 'eas', 'Interinstitutional services', 'EUSA',
  'European School of Administration',
  'The interinstitutional school that designs and delivers training for staff of all the EU institutions: management and leadership development, induction for new officials, and shared learning programmes, working alongside the training units of the institutions. It has no standalone website; its corporate documents are published on the Commission strategy-documents pages.',
  'https://commission.europa.eu/about/departments-and-executive-agencies/european-school-administration_en', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
