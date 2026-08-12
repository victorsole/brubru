-- 216_dataset_catalog_title_i18n.sql
--
-- Multilingual titles for the Brubru dataset catalogue.
--
-- brubru_dataset_catalog.description is jsonb keyed by language, so a Catalan
-- user reads Catalan prose. title is plain TEXT, English only. That gap was
-- invisible while nothing rendered the catalogue; the moment MEUB Brubru
-- Databases started showing one card per dataset, every card came out with an
-- English heading over a Catalan body.
--
-- It is also a DCAT-AP defect. dct:title is a multilingual property and the
-- serialiser in services/vocabularies/dcat_ap_serializer.py could only ever
-- emit lang="en" (its own comment says the title should come from JSONB). Any
-- portal harvesting /api/datasets.ttl gets an English-only catalogue.
--
-- title stays as the fallback and the DCAT-AP mandatory minimum, so nothing
-- breaks if a row has no title_i18n.

ALTER TABLE brubru_dataset_catalog
    ADD COLUMN IF NOT EXISTS title_i18n jsonb;

COMMENT ON COLUMN brubru_dataset_catalog.title_i18n IS
    'Dataset title keyed by ISO 639-1 language code (en, ca, es, fr, it, nl). '
    'Falls back to the title column when a language is absent.';
