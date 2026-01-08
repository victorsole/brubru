-- Add personalization fields to users table
-- Required for personalized greeting feature

ALTER TABLE users
ADD COLUMN IF NOT EXISTS first_name VARCHAR(100),
ADD COLUMN IF NOT EXISTS preferred_name VARCHAR(100),
ADD COLUMN IF NOT EXISTS timezone VARCHAR(100),
ADD COLUMN IF NOT EXISTS language VARCHAR(10);

-- Add helpful comment
COMMENT ON COLUMN users.first_name IS 'User first name for personalization';
COMMENT ON COLUMN users.preferred_name IS 'User preferred name (overrides first_name)';
COMMENT ON COLUMN users.timezone IS 'User timezone (e.g., Europe/Brussels)';
COMMENT ON COLUMN users.language IS 'User language preference (e.g., en, fr, nl)';
