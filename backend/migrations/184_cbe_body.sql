INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('cbe', 'cbe', 'Joint Undertakings', 'CBE',
  'Circular Bio-based Europe Joint Undertaking',
  'The EU public-private partnership that funds research and innovation to develop competitive circular bio-based industries in Europe, turning biomass and waste into bio-based products, materials and chemicals (succeeding the Bio-based Industries JU).',
  'https://www.cbe.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym, name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
