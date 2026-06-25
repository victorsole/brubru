-- Migration 173 (25 Jun 2026) — seed the EDPB body row for /api/v2/edpb. Idempotent.
INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('edpb', 'edpb', 'EU bodies and advisory', 'EDPB',
  'European Data Protection Board',
  'The EU body that ensures consistent application of the GDPR across the Member States: it brings together the national data-protection authorities and the EDPS, adopts guidelines, recommendations, opinions and binding decisions, runs the one-stop-shop and consistency mechanisms, and issues public consultations on data-protection guidance.',
  'https://www.edpb.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym,
    name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
