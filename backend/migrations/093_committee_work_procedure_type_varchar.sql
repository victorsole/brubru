-- 093: Convert committee_work_items.procedure_type from native enum to varchar.
--
-- Root cause this fixes: the native PG enum `proceduretypeenum` had only five
-- labels (COD/APP/CNS/NLE/INI). The scraper's _extract_procedure_type() falls
-- back to INI for anything outside the enum, so every other OEIL procedure type
-- (DEA, RSP, BUD, RPS, NLE, INL, IMM, GBD, BUI, DEC, ACI, REG, ...) was silently
-- stored as INI. Result: 463/464 rows showed procedure_type = INI even though
-- the real type sits in the procedure_ref suffix.
--
-- OEIL's procedure-type vocabulary is open-ended and evolves, so a fixed native
-- enum is the wrong model. A varchar column removes the collapse and avoids
-- future ALTER TYPE ... ADD VALUE migrations for every new type.

ALTER TABLE committee_work_items
    ALTER COLUMN procedure_type DROP DEFAULT;

ALTER TABLE committee_work_items
    ALTER COLUMN procedure_type TYPE varchar(10)
    USING procedure_type::text;

ALTER TABLE committee_work_items
    ALTER COLUMN procedure_type SET DEFAULT 'INI';

-- The proceduretypeenum type is intentionally left in place (it may be referenced
-- elsewhere). Drop manually only after confirming there are no dependents:
--   DROP TYPE IF EXISTS proceduretypeenum;
