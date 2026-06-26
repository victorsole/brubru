INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('sesar', 'sesar', 'Joint Undertakings', 'SESAR 3',
  'SESAR 3 Joint Undertaking',
  'The EU public-private partnership that funds research and innovation to modernise European air-traffic management: it develops and delivers the digital European sky, smart ATM, U-space for drones and the European ATM Master Plan, pooling EU, EUROCONTROL and industry resources.',
  'https://www.sesarju.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym, name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
