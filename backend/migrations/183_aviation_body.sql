INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('aviation', 'aviation', 'Joint Undertakings', 'Clean Aviation',
  'Clean Aviation Joint Undertaking',
  'The EU public-private partnership that funds research and innovation into low-emission and climate-neutral aircraft technologies, succeeding Clean Sky, to help decarbonise aviation in line with the European Green Deal.',
  'https://www.clean-aviation.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym, name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
