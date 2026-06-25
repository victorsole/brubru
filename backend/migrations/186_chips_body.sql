INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('chips', 'chips', 'Joint Undertakings', 'Chips',
  'Chips Joint Undertaking',
  'The EU public-private partnership that funds research, innovation and capacity building to strengthen Europes semiconductor ecosystem under the European Chips Act, including the Chips for Europe initiative and pilot lines (succeeding the Key Digital Technologies JU).',
  'https://www.chips-ju.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym, name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
