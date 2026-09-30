-- secondary_acts: carry the acts the Commission has ANNOUNCED but not yet adopted.
--
-- 322 rows of the RegDel export never reached us: 207 Planned, 109 Cancelled, 6 On hold.
-- They are dropped by normalise_row() because they have no CCode, and they have no CCode
-- because a C-number is only issued when the College adopts the act. So the register's
-- entire forward-looking pipeline -- what is coming in Q3 2026, what was cancelled -- was
-- invisible, which is precisely the question a policy client asks first.
--
-- These rows are stored with a SYNTHETIC reference, because `reference` is NOT NULL
-- UNIQUE and they have no real identifier of any kind (the register's JSON API is
-- CSRF-protected; the Excel export is the only open path and its CCode and Celex columns
-- are empty for all 322).
--
-- The synthetic value is deliberately unmistakable. It is `PLANNED:<16 hex>` and can
-- never be confused with a Commission C(YYYY)NNNN code, so nothing downstream can read it
-- as one. It is a deterministic hash of act_type + the normalised title, so a second run
-- matches the same row instead of inserting another.
--
-- Two guards, both measured against the live export on 30 Sep 2026:
--   * 7 of the 322 already exist as a real act under a C-number (the same act listed
--     twice, once planned and once published). Those are skipped: the real act wins.
--   * one title is 'Commission Implementing Regulation (*)', which carries no content to
--     key on. Titles that normalise to fewer than 25 characters are skipped and reported.
--
-- 'Planned adoption date' holds a QUARTER ("Q3 2026"), not a date, so it gets its own
-- text column. It must never be written to adoption_date: that column means the day the
-- College adopted the act, and a planned act has not been adopted.

BEGIN;

ALTER TABLE public.secondary_acts
    ADD COLUMN IF NOT EXISTS planned_adoption_period VARCHAR(16);

COMMENT ON COLUMN public.secondary_acts.planned_adoption_period IS
    'The Commission''s indicative timing for an act it has announced but not adopted, '
    'as a quarter ("Q3 2026") exactly as the RegDel register states it. Free text on '
    'purpose: it is a period, not a date, and must never be coerced into adoption_date.';

-- Finding a pipeline row by its synthetic key, and listing what is coming, are both
-- common enough to index. Partial: only 322 of 8,483 rows qualify today.
CREATE INDEX IF NOT EXISTS ix_secondary_acts_pipeline
    ON public.secondary_acts (status, planned_adoption_period)
    WHERE celex IS NULL;

COMMIT;
