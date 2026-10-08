-- 278: say whether a resolution was adopted, is still pending, or never came.
--
-- /parliament/resolutions held 35 rows with no adoption date and declared all of them
-- "not yet adopted (still tabled or close to adoption)" (8 Oct 2026). Checked against
-- OEIL, 25 of them are CLOSED: an RSP debate ("Debate in Parliament", then "End of
-- procedure in Parliament") or an objection, completed with no text adopted. Those are
-- not pending resolutions and never will be. Only 10 are genuinely pending.
--
-- One owner: scripts/backfill_resolution_dates.py, which already owns adoption_date,
-- sets this column on every run (adopted when dated; closed_without_resolution when the
-- procedure is COMPLETED with no adopted text; pending otherwise). The corpus backfill
-- inserts adopted texts only, so it writes 'adopted'.
--
-- Added with a DEFAULT so the 318 dated rows take 'adopted' without an UPDATE: an UPDATE
-- would fire trg_ep_resolutions_touch_if_changed and re-stamp updated_at on every row,
-- handing incremental-sync clients the whole corpus. The default is then dropped, so a
-- future insert that forgets the column stores NULL (caught by the owner's next run)
-- rather than silently claiming 'adopted'.
ALTER TABLE ep_resolutions
    ADD COLUMN IF NOT EXISTS status text DEFAULT 'adopted';

ALTER TABLE ep_resolutions ALTER COLUMN status DROP DEFAULT;

ALTER TABLE ep_resolutions DROP CONSTRAINT IF EXISTS ep_resolutions_status_check;
ALTER TABLE ep_resolutions ADD CONSTRAINT ep_resolutions_status_check
    CHECK (status IN ('adopted', 'pending', 'closed_without_resolution'));

COMMENT ON COLUMN ep_resolutions.status IS
    'adopted | pending | closed_without_resolution (procedure completed in Parliament with no text adopted). Owner: scripts/backfill_resolution_dates.py.';

CREATE INDEX IF NOT EXISTS idx_ep_resolutions_status ON ep_resolutions (status);
