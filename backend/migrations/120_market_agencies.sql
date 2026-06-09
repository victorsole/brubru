-- ---------------------------------------------------------------------------
-- Migration 120 — single-market / digital EU agencies (api_market.md).
--
-- Seven decentralised EU agencies, each in its OWN folder (per the agreed
-- structure), reusing the economy_bodies / economy_items store from migration
-- 119. folder = the agency's URL slug (matches body_code; eu-LISA uses the
-- 'eu_lisa' code with an 'eu-lisa' path). ON CONFLICT keeps this re-runnable.
-- ---------------------------------------------------------------------------
INSERT INTO economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('berec',   'berec', 'Single market — digital & electronic communications', 'BEREC',
   'Body of European Regulators for Electronic Communications',
   'Coordinates national telecoms regulators and advises on electronic communications.',
   'https://www.berec.europa.eu', TRUE),
 ('acer',    'acer', 'Single market — energy', 'ACER',
   'Agency for the Cooperation of Energy Regulators',
   'Coordinates national energy regulators and oversees EU energy markets (incl. REMIT).',
   'https://www.acer.europa.eu', TRUE),
 ('eit',     'eit', 'Single market — innovation', 'EIT',
   'European Institute of Innovation and Technology',
   'Strengthens EU innovation through Knowledge and Innovation Communities.',
   'https://www.eit.europa.eu', TRUE),
 ('enisa',   'enisa', 'Single market — cybersecurity', 'ENISA',
   'European Union Agency for Cybersecurity',
   'The EU agency for cybersecurity, supporting a high common level of cyber resilience.',
   'https://www.enisa.europa.eu', TRUE),
 ('eu_lisa', 'eu_lisa', 'Single market — large-scale IT', 'eu-LISA',
   'European Union Agency for the Operational Management of Large-Scale IT Systems',
   'Operates the EU large-scale IT systems in the area of freedom, security and justice.',
   'https://www.eulisa.europa.eu', TRUE),
 ('euipo',   'euipo', 'Single market — intellectual property', 'EUIPO',
   'European Union Intellectual Property Office',
   'Registers EU trade marks and registered Community designs.',
   'https://www.euipo.europa.eu', TRUE),
 ('cpvo',    'cpvo', 'Single market — plant variety rights', 'CPVO',
   'Community Plant Variety Office',
   'Grants Community plant variety rights across the EU.',
   'https://cpvo.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
