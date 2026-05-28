-- Migration 090: widen daily_briefs.source from VARCHAR(100) to VARCHAR(255).
--
-- The EFPIA daily brief uses descriptive source attributions like
--   "Official Journal, Commission Implementing Decisions 2026/1182 (Hungary)
--    and 2026/1104 (Poland), late May 2026"
-- which exceed 100 characters. The existing rows are well under 100 so the
-- widening is non-destructive.

ALTER TABLE daily_briefs
    ALTER COLUMN source TYPE VARCHAR(255);
