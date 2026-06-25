-- Migration 174 (25 Jun 2026) — seed the ECCC body row for /api/v2/eccc. Idempotent.
INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('eccc', 'eccc', 'Justice and home affairs: cybersecurity', 'ECCC',
  'European Cybersecurity Competence Centre',
  'The EU body that manages cybersecurity funding from Digital Europe and Horizon Europe and builds the EU cybersecurity community: it runs calls for proposals, coordinates the network of National Coordination Centres in the Member States, supports the Cybersecurity Competence Community, and is steered by a Governing Board of national and Commission representatives.',
  'https://cybersecurity-centre.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym,
    name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
