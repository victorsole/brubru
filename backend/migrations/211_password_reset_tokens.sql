-- 211: password reset tokens, so the login page can offer "I forgot my password".
--
-- Until now the only ways into an account were the password set at signup, an
-- OAuth identity, or a dormant-profile claim link (migration 148). A user who
-- forgot a password had no self-service route at all.
--
-- Design notes:
--   * We store sha256(token), never the token itself. A read of this table
--     therefore does not let anyone reset anybody's password.
--   * Single use: used_at is stamped on redemption and checked on every lookup.
--   * Short lived: expires_at is set an hour out by the API.
--   * The row survives redemption rather than being deleted, so the reset
--     history is auditable and the per-hour rate limit has something to count.
--
-- GRANTS DEVIATION, deliberate: the house rule for a user-owned table is
-- authenticated CRUD + service_role ALL. This table is NOT user-owned data and
-- must never be reachable from the Data API, because a client that could read
-- token_hash rows could enumerate outstanding resets. RLS is therefore enabled
-- with NO policy (deny by default) and only service_role is granted. The
-- backend reaches it through the service connection. Do not "fix" this to match
-- the standard template.

CREATE TABLE IF NOT EXISTS public.password_reset_tokens (
    id           SERIAL PRIMARY KEY,
    user_id      UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    -- sha256 hex digest of the raw token. VARCHAR not CHAR: bpchar pads to the
    -- declared width, and the SQLAlchemy model declares String(64).
    token_hash   VARCHAR(64) NOT NULL UNIQUE,
    expires_at   TIMESTAMPTZ NOT NULL,
    used_at      TIMESTAMPTZ,
    request_ip   VARCHAR(64),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Redemption path: look up by hash.
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_hash
    ON public.password_reset_tokens (token_hash);

-- Rate-limit path: count recent requests per user, and invalidate outstanding
-- tokens when a new one is issued.
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_created
    ON public.password_reset_tokens (user_id, created_at DESC);

-- Converge a table that create_all() may have built first. SQLAlchemy's
-- `default=` is applied in Python, not as a DDL DEFAULT, so a table born from
-- create_all() has created_at NOT NULL with nothing to fill it and any raw SQL
-- INSERT fails. Confirmed on production 10 Aug 2026. The CREATE TABLE above
-- gets this right, but it is skipped when the table already exists.
ALTER TABLE public.password_reset_tokens
    ALTER COLUMN created_at SET DEFAULT now();

ALTER TABLE public.password_reset_tokens ENABLE ROW LEVEL SECURITY;

-- REVOKE first, and not only for tidiness. If SQLAlchemy's create_all() got
-- here before this migration did (core/database.py:116 runs it at startup),
-- the table was born under Supabase's default privileges, which hand anon and
-- authenticated full CRUD. On this table that is an account-takeover primitive:
-- anyone able to INSERT can write token_hash = sha256(value-they-chose) against
-- any user_id and then redeem it at /api/auth/reset-password. Confirmed present
-- on 10 Aug 2026, which is why these lines exist.
REVOKE ALL ON public.password_reset_tokens FROM anon;
REVOKE ALL ON public.password_reset_tokens FROM authenticated;
REVOKE ALL ON SEQUENCE public.password_reset_tokens_id_seq FROM anon;
REVOKE ALL ON SEQUENCE public.password_reset_tokens_id_seq FROM authenticated;

-- No policy on purpose. See the grants deviation note above.
GRANT ALL ON public.password_reset_tokens TO service_role;
GRANT ALL ON SEQUENCE public.password_reset_tokens_id_seq TO service_role;
