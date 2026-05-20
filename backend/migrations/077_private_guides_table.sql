-- migrations/077_private_guides_table.sql
-- Backing store for per-user/per-org private knowledge bundles (20 May 2026).
--
-- The local source-of-truth lives in (gitignored) backend/knowledge_base/private_guides/{slug}/*.md
-- A sync script (scripts/sync_private_guides_to_db.py) UPSERTs that disk
-- content into this table, so production (Railway) can serve the bundle
-- WITHOUT shipping the markdown files in the deploy image.
--
-- Per CLAUDE.md hard rule (Supabase Data API grants mandatory, 15 May 2026):
-- explicit grants are required for every new public.* table.

BEGIN;

CREATE TABLE IF NOT EXISTS public.private_guides (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            VARCHAR(120) NOT NULL,
    filename        VARCHAR(255) NOT NULL,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    ordering        INTEGER NOT NULL DEFAULT 0,
    source_path     TEXT,            -- local disk path (debug aid)
    source_hash     VARCHAR(64),     -- sha256 of content, for cheap drift detection
    is_test         BOOLEAN NOT NULL DEFAULT FALSE,
    last_synced_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT private_guides_slug_filename_key UNIQUE (slug, filename)
);

CREATE INDEX IF NOT EXISTS idx_private_guides_slug
    ON public.private_guides(slug);
CREATE INDEX IF NOT EXISTS idx_private_guides_test
    ON public.private_guides(is_test);

-- Row-Level Security. The chat backend uses the service_role connection
-- (Brubru does not query Supabase REST as the end user), so anon and
-- authenticated never need direct access to the table. We still ENABLE RLS
-- + ship a tight policy to satisfy the rule.
ALTER TABLE public.private_guides ENABLE ROW LEVEL SECURITY;

-- No anon/authenticated SELECT — private guides are confidential per-user
-- material. Only service_role reads/writes them.
DROP POLICY IF EXISTS private_guides_service_role ON public.private_guides;
CREATE POLICY private_guides_service_role
    ON public.private_guides
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Explicit grants (per hard rule). anon/authenticated get NOTHING.
REVOKE ALL ON public.private_guides FROM anon;
REVOKE ALL ON public.private_guides FROM authenticated;
GRANT ALL ON public.private_guides TO service_role;

COMMIT;
