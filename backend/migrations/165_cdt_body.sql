-- Migration 165 (25 Jun 2026) — seed the CdT body row for the
-- /api/v2/cdt folder. Idempotent upsert.

INSERT INTO public.economy_bodies (code, folder, family, acronym, name, mandate, website, is_eu_institution) VALUES
 ('cdt', 'cdt', 'Decentralised agencies: translation', 'CdT',
  'Translation Centre for the Bodies of the European Union',
  'The EU agency that provides translation, terminology, audiovisual and language services to the other EU agencies and bodies, and manages IATE, the EUs shared interinstitutional terminology database. Based in Luxembourg, it supports multilingualism across the decentralised agencies.',
  'https://cdt.europa.eu', TRUE)
ON CONFLICT (code) DO UPDATE SET
    folder = EXCLUDED.folder, family = EXCLUDED.family, acronym = EXCLUDED.acronym,
    name = EXCLUDED.name, mandate = EXCLUDED.mandate, website = EXCLUDED.website,
    is_eu_institution = EXCLUDED.is_eu_institution;
