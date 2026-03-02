-- Migration 028: Add trainer flag to users
-- Trainers are users who stress-test Brubru and get Professional (blue) access + visual indicators

ALTER TABLE users ADD COLUMN IF NOT EXISTS is_trainer BOOLEAN DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_users_is_trainer ON users(is_trainer) WHERE is_trainer = TRUE;
