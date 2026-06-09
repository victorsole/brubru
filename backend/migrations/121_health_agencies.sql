-- ---------------------------------------------------------------------------
-- Migration 121 — EU health agencies (api_health.md).
--
-- Four decentralised EU health agencies, each in its OWN folder (per the agreed
-- structure), reusing the economy_bodies / economy_items store. folder = the
-- agency's URL slug / body_code (EU-OSHA uses code 'eu_osha' with an 'eu-osha'
-- path). EMCDDA/EUDA is deferred (URL harvest incomplete). ON CONFLICT keeps
-- this re-runnable. NB: api_health.md mislabels EMA "European Medicines
-- Alliance" — the authoritative name is European Medicines Agency.
-- ---------------------------------------------------------------------------
INSERT INTO economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('ema',     'ema', 'Health — medicines', 'EMA',
   'European Medicines Agency',
   'Scientific evaluation, supervision and safety monitoring of medicines in the EU.',
   'https://www.ema.europa.eu', TRUE),
 ('ecdc',    'ecdc', 'Health — disease prevention', 'ECDC',
   'European Centre for Disease Prevention and Control',
   'EU agency strengthening defences against infectious diseases.',
   'https://www.ecdc.europa.eu', TRUE),
 ('efsa',    'efsa', 'Health — food safety', 'EFSA',
   'European Food Safety Authority',
   'Independent scientific advice on risks in the food chain.',
   'https://www.efsa.europa.eu', TRUE),
 ('eu_osha', 'eu_osha', 'Health — occupational safety', 'EU-OSHA',
   'European Agency for Safety and Health at Work',
   'EU agency for information on occupational safety and health.',
   'https://osha.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
