-- Migration: Add Stripe fields to users table
-- Date: 2025-11-20
-- Description: Adds stripe_customer_id and stripe_subscription_id to support Stripe payments

-- Add Stripe customer ID column (unique identifier for the customer in Stripe)
ALTER TABLE users
ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255) UNIQUE;

-- Add Stripe subscription ID column (identifier for active subscription)
ALTER TABLE users
ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255);

-- Add index for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_stripe_customer_id ON users(stripe_customer_id);

-- Comment the columns
COMMENT ON COLUMN users.stripe_customer_id IS 'Stripe customer ID (unique)';
COMMENT ON COLUMN users.stripe_subscription_id IS 'Active Stripe subscription ID';
