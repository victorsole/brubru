-- Migration: Add preferences column to users table
-- Purpose: Store user preferences including tour progress, UI settings, etc.

-- Add preferences column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users'
        AND column_name = 'preferences'
    ) THEN
        ALTER TABLE users ADD COLUMN preferences JSONB DEFAULT '{}';
        RAISE NOTICE 'Added preferences column to users table';
    ELSE
        RAISE NOTICE 'preferences column already exists';
    END IF;
END $$;
