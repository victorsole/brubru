-- Migration 081: Defensive DB-side default + NOT NULL + CHECK on users.role.
--
-- Background:
--   The User SQLAlchemy model declares `role = Column(String(50), default="user")`.
--   That default is ORM-side only, NOT a Postgres DEFAULT, so any raw SQL
--   INSERT into `users` that omits the `role` column lands the row with
--   role=NULL. The auth path /api/auth/login then HTTP 500's even with a valid
--   password, because the response handler dereferences a non-nullable field.
--   First documented occurrence: Joan Pique (jmp@bassons.eu) on 20 May 2026,
--   seeded via backend/scripts/seed_jmp_acm.py which used raw SQL INSERT.
--   Discovered + backfilled 21 May 2026 (UPDATE users SET role='user' WHERE
--   email='jmp@bassons.eu'). This migration shuts the door at the DB.
--
-- Same shape as migration 080 (user_documents). Mirrors the Pydantic auth
-- schema's role allowlist of ('user', 'admin').
--
-- Pre-flight audit (verified 21 May 2026):
--   - 70 users with role='user'
--   - 1 user with role='admin'
--   - 0 users with role IS NULL
--   - 0 users with role outside the allowlist
--
-- Related but NOT in this migration (candidates for a follow-up 082 if Victor
-- wants to harden them the same way):
--   - users.subscription_tier (ORM default 'white', column nullable, no DB
--     default). Allowlist: ('white', 'yellow', 'blue').
--   - users.is_active (ORM default True, column nullable, no DB default).
--   - users.is_verified (ORM default False, column nullable, no DB default).
-- All three currently have 0 NULL rows but the next seed script that forgets
-- to set them will silently break tier checks / login.

BEGIN;

-- Step 1: DB-side default. From this point on, any INSERT into users that
-- omits the role column lands with role='user'.
ALTER TABLE public.users ALTER COLUMN role SET DEFAULT 'user';

-- Step 2: NOT NULL. No row can ever land with role=NULL again.
ALTER TABLE public.users ALTER COLUMN role SET NOT NULL;

-- Step 3: CHECK constraint pinning role to the allowlist.
-- Source of truth for the allowlist: backend/models/user.py and the auth
-- response schemas. Update Pydantic + this CHECK in a single migration if
-- a new role is introduced; never one without the other.
ALTER TABLE public.users
    DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE public.users
    ADD CONSTRAINT users_role_check
    CHECK (role IN ('user', 'admin'));

-- Step 4: COMMENT for future readers.
COMMENT ON CONSTRAINT users_role_check ON public.users IS 'Pins users.role to the application allowlist (user, admin). See migration 081 and memory/feedback_raw_insert_orm_defaults.md. Update Pydantic auth schemas AND this constraint together; never one alone.';

COMMIT;
