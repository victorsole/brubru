-- ---------------------------------------------------------------------------
-- Migration 122 — widen economy_items.item_type.
--
-- The original VARCHAR(20) fit news|publication|event|legal, but the agency
-- database resources use longer descriptive item_types (e.g.
-- 'openfoodtox_substance'). Widen to VARCHAR(60). Idempotent.
-- ---------------------------------------------------------------------------
ALTER TABLE economy_items ALTER COLUMN item_type TYPE VARCHAR(60);
