-- migrations/076_users_private_guide.sql
-- "Private guides" feature (20 May 2026).
--
-- Per-user bespoke knowledge bundle, kept in a gitignored tree under
--   backend/knowledge_base/private_guides/{slug}/*.md
-- and ALWAYS injected near the top of format_context_for_ai() for the
-- authenticated user. Used as a "Brubru already knows you" hook for
-- high-value prospects (FerrMed first, others to follow).
--
-- Three new columns on public.users:
--   * private_guide_slug       -- folder name under private_guides/
--   * private_guide_status     -- draft (do not surface yet) | ready
--                                (auto-inject) | locked (manually approved,
--                                no auto-overwrite)
--   * private_guide_updated_at -- last regenerated timestamp
--
-- Per CLAUDE.md hard rule (Supabase Data API grants mandatory, 15 May 2026):
-- the users table already has the grants applied via the auth schema; this
-- migration only adds columns, no new table, so no fresh GRANT block needed.

BEGIN;

ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS private_guide_slug TEXT,
  ADD COLUMN IF NOT EXISTS private_guide_status TEXT
    CHECK (private_guide_status IN ('draft', 'ready', 'locked')),
  ADD COLUMN IF NOT EXISTS private_guide_updated_at TIMESTAMPTZ;

-- Index only the rows that have a slug — sparse but high-value lookup
-- (every chat request for that user does this lookup).
CREATE INDEX IF NOT EXISTS idx_users_private_guide_slug
  ON public.users(private_guide_slug)
  WHERE private_guide_slug IS NOT NULL;

COMMIT;
