-- Migration 088: widen committee_meeting_transcripts.committee_code from VARCHAR(10) to VARCHAR(20)
-- Needed for joint committee codes like IMCOJURIPETI (12 chars), AFETDEVE, JURILIBE, etc.

ALTER TABLE committee_meeting_transcripts
    ALTER COLUMN committee_code TYPE VARCHAR(20);
