-- Migration 134 — 'eurojust' body so Eurojust's own procurement (ongoing calls
-- for tender + low-value contracts, the sub-threshold ones not in TED) can be
-- stored and surfaced under Funding & Tenders.
INSERT INTO economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('eurojust', 'eurojust', 'Justice & interior — criminal justice', 'Eurojust',
  'European Union Agency for Criminal Justice Cooperation',
  'The EU agency for criminal-justice cooperation; runs its own procurement (calls for tender and low/middle-value contracts).',
  'https://www.eurojust.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
