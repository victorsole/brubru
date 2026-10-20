-- 307: cohesion finances, cohesion outcomes and CAP payments keep their rows across runs (20 Oct 2026).
--
-- Their writers deleted every row of a fund and inserted it again each week, so every id changed
-- (982 finance rows held ids 16,910-17,891: the detail routes' ids were gone a week later),
-- creation_date was the last run, and the change trigger of 306 never fired (a re-insert is not an
-- UPDATE): every row would have read "changed" every week. The writers now upsert on these keys and
-- delete only the rows the source no longer lists.
--   * finances: (fund, cci, financial_allocation_category), unique on 982 of 982;
--   * CAP payments: (fund, ms), unique on 56 of 56;
--   * outcomes: no set of served columns is unique (61,992 distinct over 75,318 rows: the source
--     differs in fields Brubru does not keep), so the row's content key, md5 of its source record
--     (75,316 distinct; the 2 exact duplicates are removed).
-- The triggers are restated to ignore `raw` (the source copy, not served) and `row_key`, so only a
-- served column moves updated_at.

SET LOCAL lock_timeout = '10s';

CREATE UNIQUE INDEX IF NOT EXISTS ux_eu_cohesion_finances_row
    ON eu_cohesion_finances (fund, cci, (coalesce(financial_allocation_category, '')));

CREATE UNIQUE INDEX IF NOT EXISTS ux_eu_cap_payments_row ON eu_cap_payments (fund, ms);

ALTER TABLE eu_cohesion_outcomes ADD COLUMN IF NOT EXISTS row_key text;

DROP TRIGGER IF EXISTS trg_eu_cohesion_finances_touch ON eu_cohesion_finances;
CREATE TRIGGER trg_eu_cohesion_finances_touch BEFORE UPDATE ON eu_cohesion_finances
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', 'fetched_at,raw', 'created_at');

DROP TRIGGER IF EXISTS trg_eu_cohesion_outcomes_touch ON eu_cohesion_outcomes;
CREATE TRIGGER trg_eu_cohesion_outcomes_touch BEFORE UPDATE ON eu_cohesion_outcomes
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', 'fetched_at,raw,row_key', 'created_at');

DROP TRIGGER IF EXISTS trg_eu_cap_payments_touch ON eu_cap_payments;
CREATE TRIGGER trg_eu_cap_payments_touch BEFORE UPDATE ON eu_cap_payments
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', 'fetched_at,raw', 'created_at');

DROP TRIGGER IF EXISTS trg_eu_solidarity_fund_touch ON eu_solidarity_fund;
CREATE TRIGGER trg_eu_solidarity_fund_touch BEFORE UPDATE ON eu_solidarity_fund
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', 'fetched_at,raw', 'created_at');

-- row_key is ignored by the trigger above, so this backfill moves no updated_at.
UPDATE eu_cohesion_outcomes SET row_key = md5(raw::text) WHERE row_key IS NULL;

DELETE FROM eu_cohesion_outcomes a
 USING eu_cohesion_outcomes b
 WHERE a.fund = b.fund AND a.source_dataset = b.source_dataset AND a.row_key = b.row_key AND a.id > b.id;

CREATE UNIQUE INDEX IF NOT EXISTS ux_eu_cohesion_outcomes_row
    ON eu_cohesion_outcomes (fund, source_dataset, row_key);
