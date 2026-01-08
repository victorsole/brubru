-- Add background_preference column to users table
-- Migration: Add background_preference for personalized page backgrounds

ALTER TABLE users
ADD COLUMN IF NOT EXISTS background_preference VARCHAR(100) DEFAULT 'default';

-- Add comment
COMMENT ON COLUMN users.background_preference IS 'Background image filename for personalized page backgrounds';
