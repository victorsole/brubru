-- Migration 020: Add pre_user_id tracking for anonymous chat sessions
-- Allows linking anonymous chats to users after signup

-- Add pre_user_id column to chats table
ALTER TABLE chats ADD COLUMN IF NOT EXISTS pre_user_id VARCHAR(36);

-- Index for fast lookup when linking pre-user chats to new accounts
CREATE INDEX IF NOT EXISTS idx_chats_pre_user_id ON chats(pre_user_id) WHERE pre_user_id IS NOT NULL;

-- Allow null user_id for anonymous chats (pre-users)
ALTER TABLE chats ALTER COLUMN user_id DROP NOT NULL;
