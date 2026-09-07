-- 227_amendator_examples_is_pinned.sql
--
-- Stop the Amendator example rotation evicting the flagship acts.
--
-- Why (found 7 September 2026)
-- ----------------------------
-- scripts/rotate_amendator_examples.py enforces MAX_ACTIVE = 10 by deactivating the
-- OLDEST active row (`ORDER BY added_at ASC LIMIT 1`). It has no concept of an
-- evergreen example, so age alone decides. On 7 September rotating in the Biotech Act
-- displaced `32024R1689` -- the AI Act -- purely because it had been added on
-- 30 April. It is the single most recognised EU regulation and the best demo in the
-- list. It was restored by hand, but it landed at position 9, which made it the next
-- row to be evicted, and the DSA and GDPR sit behind it.
--
-- A curated demo list that silently degrades every week is worse than no rotation.
--
-- What this adds
-- --------------
-- `is_pinned`: a pinned row is never chosen for eviction. It does NOT exempt the row
-- from the cap; it only removes it from the eviction candidate set, so the rotation
-- displaces the oldest UNPINNED row instead.
--
-- NOT NULL DEFAULT false, so every existing row keeps today's behaviour and no code
-- reading the table needs to handle a NULL. Compare
-- feedback_null_propagation_and_silent_fallback_hide_failures: a nullable boolean in
-- a filter is how `NOT (NULL OR false)` quietly drops rows.
--
-- Safety valve
-- ------------
-- If every active row were pinned, the rotation would have nothing to evict and could
-- not add. The script must fall back to the oldest row regardless of pin in that case,
-- and say so. That is enforced in the script, not here, because it is a policy
-- decision rather than a data constraint.
--
-- Apply:  psql "$DATABASE_URL" -f backend/migrations/227_amendator_examples_is_pinned.sql
-- Safe to re-run (IF NOT EXISTS + idempotent UPDATE).

ALTER TABLE public.amendator_featured_examples
    ADD COLUMN IF NOT EXISTS is_pinned boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.amendator_featured_examples.is_pinned IS
    'Never evict this example when the rotation hits MAX_ACTIVE. Added 7 September '
    '2026 after age-based eviction displaced the AI Act. Does not exempt the row from '
    'the cap, only from the eviction candidate set.';

-- Partial index: the rotation only ever asks "which active rows are NOT pinned",
-- so index exactly that. Tiny table, but it documents the access pattern.
CREATE INDEX IF NOT EXISTS idx_amendator_examples_evictable
    ON public.amendator_featured_examples (added_at)
    WHERE is_active AND NOT is_pinned;

-- Pin the evergreens: the acts that make the Amendator legible to a first-time
-- visitor regardless of what is topical this week. Chosen because each is a
-- household name in EU tech policy AND parses with deep structure (verified
-- 7 September 2026: AI Act 1,768 elements, DSA 1,292, PPWR 1,410).
UPDATE public.amendator_featured_examples
   SET is_pinned = TRUE
 WHERE celex IN (
        '32024R1689',   -- AI Act
        '32022R2065',   -- Digital Services Act
        '32025R0040'    -- Packaging and Packaging Waste Regulation
       );

-- No RLS or GRANT changes: this alters an existing table, it does not create one.
