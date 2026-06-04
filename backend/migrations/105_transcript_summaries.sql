-- 105_transcript_summaries.sql
-- Multilingual institutional summaries for MEUB Transcripts (the moat).
-- One canonical English summary (Qwen3-30B) + on-demand translations
-- (Qwen3-235B-Instruct-2507) into ES/FR/NL/IT/CA, cached per language.
-- Shape: {"en": {"text": "...", "model": "...", "generated_at": "ISO"}, "es": {...}}
--
-- Created: 2 June 2026 (MEUB Transcripts — summaries + translation).

ALTER TABLE committee_meeting_transcripts
    ADD COLUMN IF NOT EXISTS summaries JSONB NOT NULL DEFAULT '{}'::jsonb;
