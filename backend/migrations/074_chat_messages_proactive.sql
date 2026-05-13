-- Migration 074 — Proactive Chat support (P2)
--
-- Adds two columns to chat_messages so messages that Brubru *initiates*
-- (rather than ones it answers) can be identified, audited, and rate-limited.
--
--   - is_proactive      TRUE when the assistant message was produced by the
--                       proactive trigger engine rather than as a reply to a
--                       user message.
--   - trigger_source    Free-text label for which trigger fired
--                       (morning_brief | new_file_match | tracked_file_movement
--                        | amendment_surge | other). Indexable for analytics.
--
-- Safe to re-run.

BEGIN;

ALTER TABLE chat_messages
    ADD COLUMN IF NOT EXISTS is_proactive BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE chat_messages
    ADD COLUMN IF NOT EXISTS trigger_source VARCHAR(60);

CREATE INDEX IF NOT EXISTS ix_chat_messages_is_proactive_chat_id
    ON chat_messages (chat_id, is_proactive)
    WHERE is_proactive = TRUE;

COMMIT;

-- Down migration (reference):
-- ALTER TABLE chat_messages DROP COLUMN IF EXISTS is_proactive;
-- ALTER TABLE chat_messages DROP COLUMN IF EXISTS trigger_source;
-- DROP INDEX IF EXISTS ix_chat_messages_is_proactive_chat_id;
