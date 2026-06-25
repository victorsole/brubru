INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('eda', 'eda', 'Foreign, security and defence', 'EDA',
  'European Defence Agency',
  'The EU agency that supports Member States in improving their defence capabilities through European cooperation: it runs capability development, defence research and technology, industry engagement and training and exercises, and supports the EU defence initiatives (PESCO, CARD) and operations.',
  'https://eda.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym, name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
