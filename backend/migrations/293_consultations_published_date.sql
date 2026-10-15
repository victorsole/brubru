-- 293: a Have Your Say initiative's publication date and last feedback period get their
-- own columns and one writer.
--
-- On 2 Oct 2026 scripts/backfill_consultation_dates.py read each initiative's first
-- publication date from the Commission's API and wrote it into start_date, leaving 148
-- consultations undated. The nightly sync (scripts/sync_have_your_say.py) owns start_date
-- as "the current feedback period opens" and empties it when the portal shows no current
-- period, so its run of 3 Oct erased 2,474 of those dates and /commission/consultations
-- served 2,758 of 4,892 rows with no document_date until 15 Oct, when GovClipping asked.
--
-- published_date is written only by backfill_consultation_dates.py (the earliest
-- publishedDate of the initiative's publications); the sync never names it. The API
-- serves document_date = coalesce(published_date, start_date). The BEFORE UPDATE trigger
-- (migration 245) compares every column, so filling it moves last_updated and an
-- incremental caller is handed the rows whose date appeared.

ALTER TABLE public_consultations ADD COLUMN IF NOT EXISTS published_date date;

-- GovClipping, the same day: every consultation must carry its publication date, the day
-- feedback opened and the day it closed. start_date / end_date stay the sync's (the CURRENT
-- feedback period); a closed initiative has none, so the dates job also keeps the LAST
-- period that took feedback (the latest publication with an endDate at the same API).
-- The API serves the sync's pair when it has one and this pair otherwise, never a mix.
ALTER TABLE public_consultations ADD COLUMN IF NOT EXISTS feedback_start_date date;
ALTER TABLE public_consultations ADD COLUMN IF NOT EXISTS feedback_end_date date;

COMMENT ON COLUMN public_consultations.published_date IS
    'First publication of the initiative on Have Your Say (earliest publishedDate at '
    'brpapi/groupInitiatives). Written only by scripts/backfill_consultation_dates.py.';

COMMENT ON COLUMN public_consultations.feedback_start_date IS
    'Opening of the last feedback period at brpapi/groupInitiatives (publishedDate of the latest '
    'publication with an endDate). Written only by scripts/backfill_consultation_dates.py.';
COMMENT ON COLUMN public_consultations.feedback_end_date IS
    'Close of that same feedback period (its endDate). Written only by '
    'scripts/backfill_consultation_dates.py.';
