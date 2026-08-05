-- 201_gisco_units_rls.sql
-- Close the Supabase-flagged critical hole (rls_disabled_in_public) on gisco_units.
--
-- gisco_units holds public EU administrative boundaries (Eurostat GISCO NUTS + LAU),
-- the geometry source for the GI mapping build. It was created this session via
-- geopandas.to_postgis, which does NOT enable RLS and left the legacy full default
-- grants in place: anon (the PUBLIC frontend key) held INSERT/UPDATE/DELETE/TRUNCATE
-- on all 100,198 rows. No PII, but a real integrity hole -- the anon key could wipe
-- or poison the boundary data the whole GI map depends on.
--
-- Fix = the CLAUDE.md public-read pattern (ENABLE RLS -> REVOKE excess -> POLICY -> GRANT).
-- Backend scripts connect via the direct DATABASE_URL owner role (RLS-exempt), so the
-- GI pipeline is unaffected; only the PostgREST Data API (anon/authenticated) is gated.

ALTER TABLE public.gisco_units ENABLE ROW LEVEL SECURITY;

-- strip the dangerous inherited write grants from the public roles
REVOKE ALL ON public.gisco_units FROM anon, authenticated;

DROP POLICY IF EXISTS gisco_units_public_read ON public.gisco_units;
CREATE POLICY gisco_units_public_read ON public.gisco_units
  FOR SELECT TO anon, authenticated USING (true);

-- public reference data: read-only for the API roles, full control for service_role
GRANT SELECT ON public.gisco_units TO anon, authenticated;
GRANT ALL ON public.gisco_units TO service_role;
