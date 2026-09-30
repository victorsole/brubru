-- secondary_acts.status: carry the vocabulary the source actually uses.
--
-- Found on 30 Sep 2026 while fixing the duplicate-CELEX defect. The RegDel export uses
-- TEN distinct status values; scripts/ingest_regdel_acts.py mapped SIX, and every
-- unmapped value fell through a `.get(..., "draft")` default. The result:
--
--     Objected             24 delegated acts  -> stored 'draft'   (the enum HAS 'objected')
--     Cancelled       19 + 90 acts            -> stored 'draft'
--     Planned         28 + 179 acts           -> stored 'draft'
--     Scrutiny finished     8 acts            -> stored 'draft'
--     On hold          1 +  5 acts            -> stored 'draft'
--     Notified              1 act             -> stored 'draft'
--     Adopted (urgency)     1 act             -> stored 'draft'
--     Withdrawn             8 acts            -> REJECTED, the enum had no such value
--
-- 356 acts therefore carried a status that was not theirs, and 8 could not be stored at
-- all. An objection is the single most consequential event in the life of a delegated
-- act: Parliament or Council blocking the Commission. Serving 24 of them as 'draft'
-- tells a subscriber the opposite of what happened.
--
-- The silent default is the real defect. A value the source adds tomorrow must not
-- become 'draft'; it becomes 'unknown' and the run reports it, so the gap is visible the
-- first time rather than months later (feedback_null_propagation_and_silent_fallback_hide_failures).
--
-- 'published' is left out of this migration deliberately. The map sends RegDel's
-- 'Published' (6,737 acts) to 'adopted' while the enum has had an unused 'published'
-- value since migration 038. Correcting that moves 6,737 rows and changes what an API
-- subscriber sees, so it is a decision to take openly, not a side effect of this fix.
--
-- ALTER TYPE ... ADD VALUE is not wrapped in BEGIN/COMMIT: the new labels must be
-- committed before any statement can use them.

ALTER TYPE secondary_act_status_enum ADD VALUE IF NOT EXISTS 'withdrawn';
ALTER TYPE secondary_act_status_enum ADD VALUE IF NOT EXISTS 'cancelled';
ALTER TYPE secondary_act_status_enum ADD VALUE IF NOT EXISTS 'planned';
ALTER TYPE secondary_act_status_enum ADD VALUE IF NOT EXISTS 'on_hold';
ALTER TYPE secondary_act_status_enum ADD VALUE IF NOT EXISTS 'notified';
ALTER TYPE secondary_act_status_enum ADD VALUE IF NOT EXISTS 'scrutiny_finished';

COMMENT ON COLUMN public.secondary_acts.status IS
    'Lifecycle status, mirroring the RegDel register vocabulary: draft, planned, '
    'adopted, published, objected, rejected, withdrawn, cancelled, on_hold, notified, '
    'scrutiny_finished, unknown. A status the source introduces that we do not yet map '
    'is stored as ''unknown'' and reported by the ingest, never silently as ''draft''.';
