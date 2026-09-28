-- 246: ep_resolutions adopts the guard defined in migration 245.
--
-- The table has FOUR scheduled writers. Guarding one of them (backfill_resolution_dates.py,
-- 28 Sep) left backfill_ep_resolutions_corpus.py stamping all 351 rows with a single now()
-- every run, so /parliament/resolutions?updated_from=yesterday still answered with the whole
-- corpus. A column with many writers needs one owner, and the trigger is the only place that
-- sees every write.

-- ep_resolutions: /parliament/resolutions filters ?updated_from= on updated_at.
DROP TRIGGER IF EXISTS trg_ep_resolutions_touch_if_changed ON ep_resolutions;
CREATE TRIGGER trg_ep_resolutions_touch_if_changed
    BEFORE UPDATE ON ep_resolutions
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', '', 'created_at');
