-- 291: delegated acts carry what the register says about their scrutiny.
--
-- /legislative/delegated-acts documented an objection deadline, Parliament and Council
-- scrutiny and the parent procedure, and served none of them: objection_deadline,
-- ep_scrutiny, council_scrutiny and parent_procedure_ref were empty on all 2,162 delegated
-- acts, and 43 of the 49 adopted acts (the ones still inside the objection window) had no
-- adoption date. The feed read the register's Excel export, which has no such columns.
-- Found 14 Oct 2026 auditing GovClipping's delegated-acts request.
--
-- The register's own API has them: the basic act's scrutiny period, the procedure, and
-- per act the adoption, extension, objection and early non-objection events. It does NOT
-- publish the date the scrutiny period starts (the notification to Parliament and
-- Council), so no deadline can be read. What can be stated is a lower bound: notification
-- never precedes adoption, so the period cannot end before adoption + period + extension.
-- Checked on 150 published acts: 143 of 146 appeared in the Official Journal on or after
-- that date; the other 3 a day after adoption (urgency). objection_deadline stays NULL.
--
--   scrutiny_period              the basic act's period as the register states it:
--                                '2', '3', '1', or '1/3' (1 month when the Commission
--                                adopts a supervisory authority's draft unchanged, else 3)
--   objection_deadline_earliest  adoption + shortest period + extension; NULL when the
--                                period or adoption date is unknown, or both institutions
--                                said early that they will not object
--   urgency_procedure            adopted under the urgency procedure (in force at once,
--                                objection still possible)
--   regdel_updated_at            the register's own last-change time for the record;
--   regdel_events_read_for       the value of it when the events were last read. Both are
--                                bookkeeping, so the change signal ignores them.

ALTER TABLE secondary_acts
    ADD COLUMN IF NOT EXISTS scrutiny_period varchar(16),
    ADD COLUMN IF NOT EXISTS objection_deadline_earliest date,
    ADD COLUMN IF NOT EXISTS urgency_procedure boolean,
    ADD COLUMN IF NOT EXISTS regdel_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS regdel_events_read_for timestamptz;

COMMENT ON COLUMN secondary_acts.scrutiny_period IS
    'Scrutiny period of the basic act in months, as the RegDel register states it: 1, 2, 3 or 1/3 (migration 291).';
COMMENT ON COLUMN secondary_acts.objection_deadline_earliest IS
    'Adoption date + shortest scrutiny period + extension: the objection period cannot end earlier. The register publishes no start date, so this is a lower bound, not the deadline (migration 291).';
COMMENT ON COLUMN secondary_acts.urgency_procedure IS
    'Adopted under the urgency procedure, per the RegDel register (migration 291).';

DROP TRIGGER IF EXISTS trg_secondary_acts_touch ON secondary_acts;
CREATE TRIGGER trg_secondary_acts_touch BEFORE UPDATE ON secondary_acts
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed(
        'last_updated', 'scraped_at,body_fetched_at,regdel_updated_at,regdel_events_read_for', 'first_seen');
