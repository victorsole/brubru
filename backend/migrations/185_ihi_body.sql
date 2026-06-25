INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('ihi', 'ihi', 'Joint Undertakings', 'IHI',
  'Innovative Health Initiative Joint Undertaking',
  'The EU public-private partnership that funds cross-sector health research and innovation, bringing together the pharmaceutical, medical-technology, biotechnology and digital-health industries to translate research into benefits for patients and health systems (succeeding the Innovative Medicines Initiative).',
  'https://www.ihi.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym, name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
