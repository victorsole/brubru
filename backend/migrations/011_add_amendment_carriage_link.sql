-- Migration 011: Add Legislative Carriage Link to Amendments
-- Priority #4: Amendator-Legislative Train Integration
-- This migration adds fields to link amendments to tracked legislative files

-- Add carriage_id foreign key to amendments table
ALTER TABLE amendments
ADD COLUMN IF NOT EXISTS carriage_id UUID REFERENCES legislative_carriages(id) ON DELETE SET NULL;

-- Add procedure_reference column (OEIL format: "2021/0106(COD)")
ALTER TABLE amendments
ADD COLUMN IF NOT EXISTS procedure_reference VARCHAR(50);

-- Create indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_amendments_carriage_id ON amendments(carriage_id);
CREATE INDEX IF NOT EXISTS idx_amendments_procedure_reference ON amendments(procedure_reference);

-- Comment on new columns
COMMENT ON COLUMN amendments.carriage_id IS 'Link to tracked legislative file (Priority #4 integration)';
COMMENT ON COLUMN amendments.procedure_reference IS 'OEIL procedure reference, e.g., 2021/0106(COD)';
