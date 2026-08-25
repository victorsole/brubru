-- 221: record when a user was last actually present
--
-- WHY (audit, 25 August 2026)
--
-- `users.last_login` answers "when did this person last type a password or
-- click Sign in with Google". It does NOT answer "when were they last here",
-- and the two diverge almost immediately:
--
--   * the access token lives 7 days (ACCESS_TOKEN_EXPIRE_MINUTES = 60*24*7)
--   * the frontend persists it to localStorage (zustand `persist`)
--   * POST /api/auth/refresh mints a fresh one and does NOT touch last_login
--   * the axios interceptor calls refresh silently on any 401 and retries
--
-- So a returning user can come back every day, indefinitely, while last_login
-- stays frozen at the date they first signed in.
--
-- This is not theoretical. On 24 August a session recorded "Joana last used
-- Brubru 11 August" for a client on a paid trial, derived from last_login. The
-- defensible statement was "last re-authenticated on 11 August"; whether she
-- had opened it since was simply not measurable. Founder-facing answers about
-- who is active were being drawn from a column that cannot answer the question.
--
-- WHY A SEPARATE COLUMN
--
-- last_login keeps its meaning -- it is genuinely useful to know when someone
-- last authenticated, e.g. for security review. Overloading it would destroy
-- that. last_seen_at is the presence signal, written on the cheap
-- authenticated touchpoints (token refresh, profile fetch) and throttled to at
-- most once an hour per user, so it costs roughly one UPDATE per user per
-- active hour rather than one per request.
--
-- It stays NULL for users who have not been seen since this shipped. NULL means
-- "not measured", not "not present" -- do not read a NULL here as absence.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;

COMMENT ON COLUMN users.last_seen_at IS
    'Last authenticated activity (token refresh or profile fetch), throttled to '
    'once per hour. Distinct from last_login, which records re-authentication '
    'only and stays frozen for a returning user with a valid token. NULL means '
    'not measured since 25 Aug 2026, never "absent".';

-- The activity queries filter on recency and exclude the never-seen, so a
-- partial index on the non-null values is the whole working set.
CREATE INDEX IF NOT EXISTS idx_users_last_seen_at
    ON users (last_seen_at DESC)
    WHERE last_seen_at IS NOT NULL;
