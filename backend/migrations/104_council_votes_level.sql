-- 104_council_votes_level.sql
-- MEUB Votes — "Council results" tab.
--
-- The ep_roll_call_votes.level CHECK (migration 098) only allowed
-- ('committee', 'plenary'). Council of the EU legislative voting results
-- (sync_council_votes, level='council', per-member-state breakdown in
-- country_breakdown) need a third allowed value.
--
-- No new table, no new grants (098 already granted anon/authenticated SELECT
-- + service_role ALL on ep_roll_call_votes / ep_roll_call_records).

ALTER TABLE ep_roll_call_votes DROP CONSTRAINT IF EXISTS ep_roll_call_votes_level_check;

ALTER TABLE ep_roll_call_votes
    ADD CONSTRAINT ep_roll_call_votes_level_check
    CHECK (level IN ('committee', 'plenary', 'council'));
