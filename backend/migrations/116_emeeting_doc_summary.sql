-- Migration 116 — on-demand AI summary of an eMeeting document (minutes first)
--
-- Co-locates a cached plain-language summary with the extracted text in
-- emeeting_doc_text_cache (keyed by the immutable PDF URL). Generated on demand
-- via the open-source HF Qwen engine. Read-only public data; the table already
-- carries the Supabase grant block from migration 115, so only columns are added.
BEGIN;
ALTER TABLE emeeting_doc_text_cache ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE emeeting_doc_text_cache ADD COLUMN IF NOT EXISTS summary_engine TEXT;
ALTER TABLE emeeting_doc_text_cache ADD COLUMN IF NOT EXISTS summarised_at TIMESTAMPTZ;
COMMIT;
