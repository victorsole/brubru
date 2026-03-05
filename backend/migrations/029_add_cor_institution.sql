-- Migration 029: Add Committee of the Regions (CoR) to EU Calendar
-- Adds COR to institution_enum and EESC for completeness
-- Created: March 2026

-- Add COR to institution_enum
DO $$ BEGIN
    ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'COR';
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Add EESC to institution_enum (European Economic and Social Committee)
DO $$ BEGIN
    ALTER TYPE institution_enum ADD VALUE IF NOT EXISTS 'EESC';
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
