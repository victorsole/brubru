INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('esdc', 'esdc', 'Foreign, security and defence', 'ESDC',
  'European Security and Defence College',
  'The EU network college that provides training and education in the field of the Common Security and Defence Policy: it networks national institutes, defence academies and EU bodies to train civilian and military personnel for CSDP missions and operations, and runs configurations on cyber, climate and security, military Erasmus, a doctoral school and more.',
  'https://www.esdc.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym, name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
