-- Migration 167 (25 Jun 2026) — seed the CJEU body row for the
-- /api/v2/cjeu folder (api_ecj.md). Idempotent upsert.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('cjeu', 'cjeu', 'Institutions', 'CJEU',
  'Court of Justice of the European Union',
  'The EU judicial institution, comprising the Court of Justice and the General Court: it ensures that EU law is interpreted and applied uniformly across the Member States, ruling on preliminary references from national courts, actions for annulment and failure to act, infringement actions and appeals. It publishes its judgments, Advocate General opinions and orders (the EU case-law), press releases and the judicial calendar.',
  'https://curia.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
