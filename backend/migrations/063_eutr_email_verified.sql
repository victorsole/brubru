-- 063: Add email_verified flag to transparency_register_orgs + clean data
--
-- Context (11 May 2026 incident):
-- The 11 May Brubru Brief transition send bounced heavily because the
-- contact_email column was polluted with synthetic 'info@<domain>' guesses
-- for orgs that never had a verified email in their EUTR profile.
--
-- This migration adds the flag, marks the named-prefix rows as verified,
-- and NULLs out the 7208 empty-string rows so the IS NOT NULL filter in
-- send pipelines stops letting them through.

BEGIN;

-- 1. Add the verification flag (default false = unverified)
ALTER TABLE transparency_register_orgs
  ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS email_verification_source TEXT;

-- 2. NULL out empty-string contact_emails (~7208 rows)
-- These were never real emails, just placeholders that slipped past the
-- 'IS NOT NULL' filter because they were empty strings, not NULL.
UPDATE transparency_register_orgs
SET contact_email = NULL,
    updated_at = NOW()
WHERE contact_email IS NOT NULL
  AND TRIM(contact_email) = '';

-- 3. Mark named-prefix emails as verified (came from the published EUTR
-- profile, not from a synthetic info@ fallback). These are the ~47 rows
-- with prefixes like: secretariat, secretary, prensa, comunicacion,
-- press, communications, dpo, sales.europe, contact.canada, etc.
--
-- NOTE: The flag is SEMANTIC (came from EUTR profile vs guessed); it does
-- NOT imply the address is currently deliverable. Send pipelines must
-- combine both filters: email_verified=true AND outreach_status NOT IN
-- ('bounced','unsubscribed').
UPDATE transparency_register_orgs
SET email_verified = true,
    email_verified_at = NOW(),
    email_verification_source = 'eutr_published_profile',
    updated_at = NOW()
WHERE contact_email IS NOT NULL
  AND contact_email LIKE '%@%'
  AND LOWER(SUBSTRING(contact_email FROM '^[^@]+')) NOT IN (
    'info', 'contact', 'hello', 'mail', 'admin', 'office',
    'enquiries', 'inquiries', 'kontakt', 'infos'
  );

-- 4. Index to make send-pipeline filters fast
CREATE INDEX IF NOT EXISTS idx_eutr_email_verified
  ON transparency_register_orgs (email_verified)
  WHERE email_verified = true;

COMMIT;

-- Verify:
-- SELECT email_verified, COUNT(*) FROM transparency_register_orgs GROUP BY email_verified;
-- Expected: ~48 verified, rest unverified (info@* + already-bounced rows).
