-- 237: chat_validations records every answer's validator OUTCOME (23 Sep 2026).
--
-- Two ways a verdict that never happened read as a pass:
--   1. The validator fails soft: on a timeout or a provider error it returns
--      passed=true with `error` set. 80 of 428 rows were exactly that, so every
--      pass rate read off this table counted 19% unjudged answers as passed.
--   2. An answer the pre-filter skipped, or one that hit the caller's time
--      budget, wrote NO row, so "no row" meant skipped, timed out or broken
--      and nobody could tell which (audit 23 Sep: 5 of 10 answers had none).
--
-- `outcome` is judged | skipped | timeout | error, and `passed` is NULL for
-- anything not judged: untested must not read as healthy.
-- Existing table: RLS and grants unchanged.

ALTER TABLE chat_validations ADD COLUMN IF NOT EXISTS outcome TEXT NOT NULL DEFAULT 'judged';
ALTER TABLE chat_validations ALTER COLUMN passed DROP NOT NULL;

UPDATE chat_validations
   SET outcome = CASE WHEN error = 'timeout' THEN 'timeout' ELSE 'error' END,
       passed = NULL
 WHERE error IS NOT NULL AND outcome = 'judged';

ALTER TABLE chat_validations DROP CONSTRAINT IF EXISTS chat_validations_outcome_check;
ALTER TABLE chat_validations ADD CONSTRAINT chat_validations_outcome_check
  CHECK (outcome IN ('judged', 'skipped', 'timeout', 'error'));
ALTER TABLE chat_validations DROP CONSTRAINT IF EXISTS chat_validations_passed_iff_judged;
ALTER TABLE chat_validations ADD CONSTRAINT chat_validations_passed_iff_judged
  CHECK ((outcome = 'judged') = (passed IS NOT NULL));

CREATE INDEX IF NOT EXISTS idx_chat_validations_outcome_created
  ON chat_validations (outcome, created_at DESC);
