-- 048_eu_vocabularies_down.sql
--
-- Reversal of 048_eu_vocabularies.sql. Drops both tables and the trigger.

DROP TRIGGER IF EXISTS brubru_dataset_catalog_updated_at_trigger ON brubru_dataset_catalog;
DROP FUNCTION IF EXISTS trg_brubru_dataset_catalog_updated_at();

DROP TABLE IF EXISTS brubru_dataset_catalog;
DROP TABLE IF EXISTS eu_authority_labels;
