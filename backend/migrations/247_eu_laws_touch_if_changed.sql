-- 247: eu_laws carried the same unconditional stamp as public_consultations did.
--
-- /api/v1/laws answers ?updated_from= off eu_laws.updated_at, and the table's BEFORE
-- UPDATE trigger set that column to now() on every update. Nothing had touched eu_laws
-- in the 24 hours this was measured, so it read as healthy; the next bulk write over
-- the corpus (a full-text backfill, a CELEX correction) would have reported every row
-- it touched as "changed" to an incremental caller. Same defect as migration 245, found
-- before a caller hit it rather than after.
--
-- update_updated_at_column() is shared with user_consultation_inputs and storage.objects,
-- so the function stays as it is and only the eu_laws trigger is rebound.

DROP TRIGGER IF EXISTS update_eu_laws_updated_at ON eu_laws;
CREATE TRIGGER update_eu_laws_updated_at
    BEFORE UPDATE ON eu_laws
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', '', 'created_at');
