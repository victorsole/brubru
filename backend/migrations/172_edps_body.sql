-- Migration 172 (25 Jun 2026) — seed the EDPS body row for /api/v2/edps. Idempotent.
INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('edps', 'edps', 'EU bodies and advisory', 'EDPS',
  'European Data Protection Supervisor',
  'The EU independent data-protection authority: it supervises the processing of personal data by the EU institutions and bodies, advises on data-protection legislation through opinions, monitors new technologies (TechDispatch, TechSonar), handles complaints and investigations, and supports the network of EU institution data-protection officers.',
  'https://www.edps.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym,
    name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
