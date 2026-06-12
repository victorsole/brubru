-- Migration 133 — 'efca' body for the European Fisheries Control Agency, so its
-- decentralised procurement (tenders + calls for expression of interest) can be
-- stored in economy_items and surfaced under the Funding & Tenders folder.
INSERT INTO economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('efca', 'efca', 'Justice & social — fisheries control', 'EFCA',
  'European Fisheries Control Agency',
  'The EU agency coordinating fisheries control and inspection; runs its own public procurement (calls for tender, negotiated procedures, calls for expression of interest).',
  'https://www.efca.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
