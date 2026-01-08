-- Migration: Add authentication fields to users table
-- Date: 2025-01-08
-- Description: Adds password_hash and oauth_provider fields for authentication

-- Add password_hash column (nullable for OAuth users)
ALTER TABLE users
ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);

-- Add oauth_provider column (tracks Google, LinkedIn, EU Login)
ALTER TABLE users
ADD COLUMN IF NOT EXISTS oauth_provider VARCHAR(50);

-- Update subscription_tier default from 'free' to 'white' for existing users
UPDATE users
SET subscription_tier = 'white'
WHERE subscription_tier = 'free';

-- Add comment for documentation
COMMENT ON COLUMN users.password_hash IS 'Hashed password for email/password authentication (nullable for OAuth users)';
COMMENT ON COLUMN users.oauth_provider IS 'OAuth provider: google, linkedin, eu_login (nullable for email/password users)';
