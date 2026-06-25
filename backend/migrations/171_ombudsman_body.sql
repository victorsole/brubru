-- Migration 171 (25 Jun 2026) — seed the European Ombudsman body row for /api/v2/ombudsman. Idempotent.
INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('ombudsman', 'ombudsman', 'EU bodies and advisory', 'Ombudsman',
  'European Ombudsman',
  'The independent body that investigates complaints about maladministration in the EU institutions, bodies, offices and agencies: it handles citizen and organisation complaints, opens own-initiative and strategic inquiries (on transparency, access to documents, ethics and fundamental rights), and coordinates the European Network of Ombudsmen.',
  'https://www.ombudsman.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym,
    name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
