-- 103_transcript_institution.sql
-- Generalise committee_meeting_transcripts beyond EP committees: an institution
-- tag so the same table + ASR pipeline + on-demand surface can hold EP committee,
-- Commission (EbS) and Council recordings. committee_code holds the body code
-- (EP committee / Commission DG / Council configuration) per institution.
--
-- Created: 1 June 2026 (MEUB Transcripts — Commission + Council adapters).

ALTER TABLE committee_meeting_transcripts
    ADD COLUMN IF NOT EXISTS institution VARCHAR(20) NOT NULL DEFAULT 'EP';

CREATE INDEX IF NOT EXISTS ix_cmt_institution ON committee_meeting_transcripts (institution);
