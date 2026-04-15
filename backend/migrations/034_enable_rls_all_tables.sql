-- Migration 034: Enable Row-Level Security on all public tables
--
-- Context (15 April 2026): Supabase security audit flagged all 75 tables as
-- "rls_disabled_in_public" -- anyone with the project URL + anon key could
-- read/write/delete any data via the PostgREST endpoint at
-- https://{project}.supabase.co/rest/v1/*
--
-- Fix: ENABLE RLS on every table with NO policies. Since Brubru's backend
-- connects as the `postgres` role (rolbypassrls=true), all existing backend
-- queries continue to work. PostgREST/anon-key requests are now denied by
-- default (RLS + no policies = deny all).
--
-- Idempotent: ALTER TABLE ... ENABLE ROW LEVEL SECURITY is safe to run
-- multiple times -- if already enabled, it is a no-op.
--
-- Verification after apply:
--   SELECT COUNT(*) FROM pg_class c
--   JOIN pg_namespace n ON n.oid = c.relnamespace
--   WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relrowsecurity = false;
--   -- expect 0

BEGIN;

ALTER TABLE public.admin_activity_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.amendment_alignment_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.amendment_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.amendments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.analysis_exports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.carriage_status_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.catalan_translations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_example_prompts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cluster_laws ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.commission_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.commission_followups ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.committee_minutes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.committee_work_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.committee_work_status_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.compliance_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.compliance_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.consultation_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.consultation_status_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_brief_sends ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_briefs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ep_resolutions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.eprs_publications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.eu_calendar_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.eu_laws ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.feedback_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.feedback_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.gap_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.industrial_ecosystem_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_gaps ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.law_clusters ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.law_requirements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.legislative_carriages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.legislative_packages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.legislative_trains ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mep_amendments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.newsletters_content ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.newsletters_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notified_bodies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.org_intelligence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pre_user_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.public_consultations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.requirement_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resolution_to_legislation ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rss_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rss_feeds ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.technical_regulations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tender_fetch_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tender_matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tender_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenderator_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.texts_adopted ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trade_barrier_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transparency_register_orgs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_calendar_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_carriage_tracks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_commission_doc_tracks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_committee_work_tracks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_consultation_inputs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_consultation_tracks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_feed_reads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_feed_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_newsletter_interactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_newsletter_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_newsletter_topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_saved_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_text_adopted_tracks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

COMMIT;

-- Verify: run after apply
-- SELECT c.relname, c.relrowsecurity FROM pg_class c
-- JOIN pg_namespace n ON n.oid = c.relnamespace
-- WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relrowsecurity = false;
