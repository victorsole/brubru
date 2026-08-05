-- 201b — RUN THIS IN THE SUPABASE SQL EDITOR (not via the app / migration runner).
--
-- spatial_ref_sys is the PostGIS SRID reference table. It is owned by supabase_admin,
-- so the application's pooler role CANNOT alter its grants or RLS (a REVOKE from the
-- app connection silently no-ops with a warning). The Supabase SQL editor runs as a
-- privileged role that CAN.
--
-- The real (small) risk: anon/authenticated ship with full write grants here, so the
-- public anon key could TRUNCATE/modify the SRID table and break coordinate transforms.
-- Prefer REVOKE over ENABLE RLS: enabling RLS on spatial_ref_sys can interfere with
-- PostGIS functions (ST_Transform) that read it, whereas revoking the public write
-- grants removes the risk cleanly and keeps reads working.

REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
  ON public.spatial_ref_sys FROM anon, authenticated;

-- (Optional, only if you want the advisor warning itself to disappear — test that
--  ST_Transform still works afterwards; some projects prefer to leave RLS off here:)
-- ALTER TABLE public.spatial_ref_sys ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY spatial_ref_sys_read ON public.spatial_ref_sys
--   FOR SELECT TO anon, authenticated USING (true);
