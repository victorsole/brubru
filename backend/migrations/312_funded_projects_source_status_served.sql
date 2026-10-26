-- 312: the funded projects' source status word is served (26 Oct 2026), so a change to it is a change.
--
-- Migration 311 kept source_status out of the change signal because it was then a copy of status that
-- nobody was served. The item routes now return it (a `status=signed` result showed planned, ongoing
-- or ended with no visible reason), so a re-read that changes only the source's word must move
-- last_updated, or an incremental sync never sees it: the trigger is restated without it.
-- The 11 'unknown' were the CORDIS loader's placeholder for an empty status (all FP7, all ended by
-- their dates), not a word CORDIS gave: they become NULL first, while the old trigger still ignores
-- the column, since nobody was served them.

SET LOCAL lock_timeout = '10s';

UPDATE ft_funded_projects SET source_status = NULL WHERE source_status = 'unknown';

DROP TRIGGER IF EXISTS trg_ft_funded_projects_touch ON ft_funded_projects;
CREATE TRIGGER trg_ft_funded_projects_touch BEFORE UPDATE ON ft_funded_projects
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', '');
