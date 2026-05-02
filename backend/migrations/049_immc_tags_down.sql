-- Reversal of 049_immc_tags.sql
DROP INDEX IF EXISTS ix_legcarr_immc_events;
ALTER TABLE legislative_carriages DROP COLUMN IF EXISTS immc_tags;
