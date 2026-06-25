INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('satcen', 'satcen', 'Foreign, security and defence', 'SatCen',
  'European Union Satellite Centre',
  'The EU agency that provides geospatial intelligence products and services from the analysis of satellite imagery and collateral data: it supports EU decision-making and action in the field of the Common Foreign and Security Policy, including CSDP missions and operations, crisis response, border and maritime surveillance and treaty monitoring.',
  'https://www.satcen.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym, name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
