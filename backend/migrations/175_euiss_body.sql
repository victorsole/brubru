INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('euiss', 'euiss', 'Foreign, security and defence', 'EUISS',
  'European Union Institute for Security Studies',
  'The EU agency that is its foreign, security and defence policy think tank: it produces analysis (briefs, Chaillot Papers, commentary, books), runs projects and convenes events on EU foreign policy, security and defence, global governance, transnational challenges and strategic foresight to support EU decision-makers.',
  'https://www.iss.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET folder=EXCLUDED.folder, family=EXCLUDED.family, acronym=EXCLUDED.acronym, name=EXCLUDED.name, mandate=EXCLUDED.mandate, website=EXCLUDED.website, is_eu_institution=EXCLUDED.is_eu_institution;
