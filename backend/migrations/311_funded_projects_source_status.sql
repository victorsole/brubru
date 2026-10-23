-- 311: ft_funded_projects keeps the source's own status word beside one served status (23 Oct 2026).
--
-- Two writers filled `status` with two vocabularies: the CORDIS loader (FP7, H2020, Horizon Europe)
-- closed / signed / terminated / unknown, the F&T Portal loader (every other programme) Ended /
-- Ongoing / Forthcoming / Suspended. "signed" is a contract state, not a phase (of 22,735, 180 had
-- not started, 14,044 were running, 8,511 had ended), and the F&T words were last read on 15 Jun,
-- so 1,695 "Ongoing" projects had ended and 232 "Forthcoming" ones had started.
-- The served `status` becomes one vocabulary (planned | ongoing | ended | terminated | suspended |
-- unknown), set by services/funding/project_status.py from the source word and the project's own
-- dates; the source word stays here, not served, for the rule and for audits. Copying it moves no
-- change signal: the trigger is restated to ignore source_status.

SET LOCAL lock_timeout = '10s';

ALTER TABLE ft_funded_projects ADD COLUMN IF NOT EXISTS source_status VARCHAR(32);

DROP TRIGGER IF EXISTS trg_ft_funded_projects_touch ON ft_funded_projects;
CREATE TRIGGER trg_ft_funded_projects_touch BEFORE UPDATE ON ft_funded_projects
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at,source_status', '');

-- The copy. The trigger reads each row in full, so on production (109,636 rows) one statement passed
-- the role's 2-minute statement timeout; it ran there in chunks of 2,000 ids, one transaction each.
-- On a replay the statement below does the same work.
SET LOCAL statement_timeout = 0;
UPDATE ft_funded_projects SET source_status = status WHERE source_status IS NULL;
