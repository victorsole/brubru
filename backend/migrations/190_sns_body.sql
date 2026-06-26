INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('sns', 'sns', 'Joint Undertakings', 'SNS',
  'Smart Networks and Services Joint Undertaking',
  'The EU public-private partnership that funds research and innovation in smart networks and services (5G evolution and 6G) under Horizon Europe, building European leadership and supply-chain sovereignty in next-generation connectivity.',
  'https://smart-networks.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym, name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
