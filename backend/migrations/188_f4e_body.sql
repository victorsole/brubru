INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('f4e', 'f4e', 'Joint Undertakings', 'F4E',
  'Fusion for Energy',
  'The EU Joint Undertaking that manages Europes contribution to ITER, the international fusion-energy experiment, and to the Broader Approach activities with Japan: it procures the high-technology components Europe supplies to ITER and develops the European fusion-industry supply chain.',
  'https://fusionforenergy.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym, name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
