-- Migration 073 — Extend user profile for the Monitoring overhaul (P1b)
--
-- Adds two profile signals consumed by the Dashboard cockpit:
--   - role_title    Free-text professional role (e.g. "Policy officer",
--                   "MEP staffer", "EU affairs consultant"). Distinct from
--                   the auth `role` column which is user/admin only.
--   - sectors       JSONB array of EU economic-activity sector slugs
--                   the user works in (controlled vocabulary on the frontend).
--
-- Both columns are nullable. Existing users see no behavioural change until
-- they fill them in. The Dashboard's profile_completeness score factors
-- these in once present.
--
-- Safe to re-run: every ALTER uses IF NOT EXISTS / DO blocks.

BEGIN;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS role_title VARCHAR(120);

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS sectors JSONB;

-- Optional helper index for sector-based affinity queries. JSONB GIN
-- supports `@>` and `?|` containment operators we may use later.
CREATE INDEX IF NOT EXISTS ix_users_sectors_gin
    ON users USING GIN (sectors);

COMMIT;

-- Down migration (manual, kept inline for reference):
-- ALTER TABLE users DROP COLUMN IF EXISTS role_title;
-- ALTER TABLE users DROP COLUMN IF EXISTS sectors;
-- DROP INDEX IF EXISTS ix_users_sectors_gin;
