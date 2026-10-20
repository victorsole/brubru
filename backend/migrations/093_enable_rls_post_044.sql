-- Migration 093: Enable RLS on tables added since migration 044 (30 April 2026)
-- Created: 01 June 2026
-- Trigger: Monthly RLS audit (1st of every month, 09:00 Brussels)
--
-- Why this is safe for Brubru:
-- - Backend connects as `postgres` role with rolbypassrls=true → RLS is invisible to the app
-- - PostgREST / Realtime / GraphQL / Storage all respect RLS → with RLS on + no policies,
--   every anonymous request is denied (closes the rest/v1/* exposure path)
-- - Net effect: app behaviour unchanged; the anonymous Supabase REST exposure path is closed
--
-- Reference: memory/feedback_supabase_rls.md
-- This is the third RLS sweep — every NEW public.* table since 044 is included here.
-- Going forward: enforce the "ALTER TABLE … ENABLE ROW LEVEL SECURITY in the same migration
-- as CREATE TABLE" rule (CLAUDE.md learned rule, set 15 May 2026).
--
-- Tables audited (migrations 045–092). 30 were already correctly protected; 1 gap found:
--   efpia_scraped_items  (migration 092, 28 May 2026) — missing ENABLE ROW LEVEL SECURITY

ALTER TABLE public.efpia_scraped_items ENABLE ROW LEVEL SECURITY;

-- Verify after apply:
-- SELECT c.relname, c.relrowsecurity FROM pg_class c JOIN pg_namespace n ON c.relnamespace = n.oid
--  WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relrowsecurity = false ORDER BY c.relname;
-- Expected: 0 rows.
