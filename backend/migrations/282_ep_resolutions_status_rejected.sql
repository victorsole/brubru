-- 282: a resolution Parliament voted DOWN is 'rejected', never 'adopted'.
--
-- 2025/2138(INI), the European Ombudsman's annual report 2024, was served as adopted on
-- 12 March 2026 (8 Oct 2026). EP Open Data records the final vote, "Motion for a
-- resolution (as a whole)", as REJECTED, 233 for / 250 against / 76 abstentions, and no
-- adopted text exists. The adoption date had been taken from OEIL's "Decision by
-- Parliament" event, which marks a decision either way.
--
-- 'rejected' is set by scripts/sync_texts_adopted_final_votes.py (it reads the final
-- vote) and only on a procedure with no adopted text; backfill_resolution_dates.py keeps
-- it unless an adopted text appears. A rejected resolution keeps its final tally.
ALTER TABLE ep_resolutions DROP CONSTRAINT IF EXISTS ep_resolutions_status_check;
ALTER TABLE ep_resolutions ADD CONSTRAINT ep_resolutions_status_check
    CHECK (status IN ('adopted', 'pending', 'closed_without_resolution', 'rejected'));

COMMENT ON COLUMN ep_resolutions.status IS
    'adopted | pending | closed_without_resolution (ended in Parliament with no text put to a final vote) | rejected (final vote lost). Owners: backfill_resolution_dates.py; rejected set by sync_texts_adopted_final_votes.py.';
