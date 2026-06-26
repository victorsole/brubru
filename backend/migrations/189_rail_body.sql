INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('rail', 'rail', 'Joint Undertakings', 'Europes Rail',
  'Europes Rail Joint Undertaking',
  'The EU public-private partnership that funds research and innovation to deliver an integrated, digital and sustainable European railway network, through an innovation pillar and a system pillar (succeeding Shift2Rail).',
  'https://rail-research.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym, name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
