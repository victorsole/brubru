-- 284: an EU Solidarity Fund case keeps its id (and its created_at) across refreshes.
--
-- /api/v2/funding/eusf documents `id` as a "Stable Brubru row id", but
-- scripts/backfill_eusf.py ran `DELETE FROM eu_solidarity_fund` and re-inserted every case
-- on each weekly run, so all 203 cases got a new serial id (and a new creation_date)
-- every week: ids 3046-3248 for 203 rows after ~15 reloads (9 Oct 2026). Same class as
-- the transparency meetings (migration 283), found auditing ids for GovClipping.
--
-- Identity: the CCI number alone is not enough (2020GR16SPO002 covers two disasters, Cyclone
-- Ianos and the Evia floods; one 2007 Italian case has no CCI), so a case is CCI + name.
-- GENERATED so no writer can forget it; the job now upserts on it and touches updated_at
-- only when the content changes.
ALTER TABLE eu_solidarity_fund
    ADD COLUMN IF NOT EXISTS case_key text GENERATED ALWAYS AS (
        coalesce(cci_number, '') || '|' || coalesce(name_of_disaster, '')
    ) STORED;

CREATE UNIQUE INDEX IF NOT EXISTS ux_eu_solidarity_fund_case_key ON eu_solidarity_fund (case_key);

COMMENT ON COLUMN eu_solidarity_fund.case_key IS
    'Identity of an EUSF case: CCI number + disaster name (one CCI can cover two disasters). Unique; the refresh upserts on it, so a case keeps its id.';
