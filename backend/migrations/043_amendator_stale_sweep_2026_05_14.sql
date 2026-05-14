-- =============================================================================
-- Migration 043: Amendator Featured Examples — 14-day Staleness Sweep
-- =============================================================================
-- Audit performed by remote agent on 2026-05-14. Do not re-apply.
--
-- Context: Migration 042 seeded 10 items on 2026-04-30. Zero /news rotations
-- occurred in the 14 days since creation. As of 2026-05-14, all items are only
-- 14 days old — none cross the 30-day stale threshold. This migration is
-- therefore a FUTURE-SAFE script: deactivation WHERE clause is correct but
-- will match 0 rows today. Apply after 2026-05-30 for first real effect, or
-- after any /news run has added items that are subsequently aged out.
--
-- Safe to apply now: the deactivation block is idempotent and row-harmless
-- when no items qualify. The position repack IS meaningful today if any
-- in-between deactivations happened at the DB level between 30 Apr and now.
--
-- Steps:
--   1. Soft-deactivate stale non-manual active entries (added > 30 days ago)
--   2. Re-pack position for remaining active rows (ordered by added_at DESC,
--      so most recent = position 0)
-- =============================================================================

BEGIN;

-- Step 1: Soft-deactivate stale non-manual items
-- Protects source='manual' items (user-curated, never auto-expire).
UPDATE public.amendator_featured_examples
   SET is_active       = FALSE,
       deactivated_at  = NOW()
 WHERE is_active       = TRUE
   AND source         != 'manual'
   AND added_at        < NOW() - INTERVAL '30 days';

-- Step 2: Re-pack positions for remaining active rows.
-- Assigns position 0..N-1 ordered by added_at DESC (newest first = lowest position).
WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (ORDER BY added_at DESC) - 1 AS new_pos
      FROM public.amendator_featured_examples
     WHERE is_active = TRUE
)
UPDATE public.amendator_featured_examples t
   SET position = r.new_pos
  FROM ranked r
 WHERE t.id = r.id
   AND t.position != r.new_pos;  -- skip no-op updates

COMMIT;
