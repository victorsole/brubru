-- Migration 168 (25 Jun 2026) — seed the ECA body row for the
-- /api/v2/eca folder (api_eca.md). Idempotent upsert.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('eca', 'eca', 'Institutions', 'ECA',
  'European Court of Auditors',
  'The EUs independent external auditor: it checks that EU funds are correctly raised and spent, assesses whether they achieve value for money, and reports its findings to the EU institutions and the public. It publishes special reports, reviews, opinions and the annual report on the implementation of the EU budget, supporting accountability and sound financial management.',
  'https://www.eca.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
