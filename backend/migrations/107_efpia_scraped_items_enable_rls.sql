-- Migration 107: enable RLS on efpia_scraped_items (security fix).
--
-- Migration 092 created the table and added GRANTs but skipped ENABLE ROW
-- LEVEL SECURITY + a policy, so Supabase flagged it as
-- rls_disabled_in_public (critical) on 31 May 2026: a public-schema table
-- exposed through PostgREST with RLS off.
--
-- This table is tenant-internal. It is read and written ONLY through the
-- backend's own SQLAlchemy connection (api/efpia.py + services/efpia_scraper.py
-- via db.execute(...)), which connects as the app owner role and bypasses RLS.
-- Nothing reaches it through the Supabase Data API (anon/authenticated). So we
-- lock it to service_role: with RLS on and only a service_role policy, any
-- anon/authenticated PostgREST request returns zero rows, while the backend is
-- unaffected.
--
-- Order per memory/feedback_supabase_data_api_grants.md:
--   ENABLE RLS -> CREATE POLICY -> GRANT.

ALTER TABLE efpia_scraped_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS efpia_scraped_items_service_role_all ON efpia_scraped_items;
CREATE POLICY efpia_scraped_items_service_role_all
    ON efpia_scraped_items
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Re-state grants for replay safety (staging spin-up / restore / new env).
-- The authenticated SELECT grant from 092 is intentionally NOT carried over:
-- with RLS on and no authenticated policy it would be inert anyway, and no
-- code path reads this table via the authenticated Data API.
REVOKE ALL ON efpia_scraped_items FROM authenticated;
GRANT ALL ON efpia_scraped_items TO service_role;
