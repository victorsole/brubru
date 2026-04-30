-- Migration 044: Enable RLS on tables added since migration 034 (15 April 2026)
-- Created: 30 April 2026
-- Trigger: Supabase security alert dated 28 April 2026 (rls_disabled_in_public)
--
-- Why this is safe for Brubru:
-- - Backend connects as `postgres` role with rolbypassrls=true → RLS is invisible to the app
-- - PostgREST / Realtime / GraphQL / Storage all respect RLS → with RLS on + no policies,
--   every anonymous request is denied (closes the rest/v1/* exposure path)
-- - Net effect: app behaviour unchanged; the lpxzclzwciqciicpcecu.supabase.co/rest/v1/* leak path is closed
--
-- Reference: memory/feedback_supabase_rls.md + commit a3e92440 (15 April 2026 sweep)
-- This is the second RLS sweep — every NEW public.* table since 034 is included here.
-- Going forward: enforce the "ALTER TABLE … ENABLE ROW LEVEL SECURITY in the same migration as CREATE TABLE" rule.

ALTER TABLE public.citation_verifications        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.committee_meeting_transcripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ep_committee_votes            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ep_data_imports               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ep_delegations                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ep_group_memberships          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ep_member_votes               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ep_members                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ep_political_groups           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ep_sections                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ep_votes                      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resolution_mep_votes          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_vote_tracks              ENABLE ROW LEVEL SECURITY;

-- Verify after apply:
-- SELECT c.relname, c.relrowsecurity FROM pg_class c JOIN pg_namespace n ON c.relnamespace = n.oid
--  WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relrowsecurity = false ORDER BY c.relname;
-- Expected: 0 rows.
