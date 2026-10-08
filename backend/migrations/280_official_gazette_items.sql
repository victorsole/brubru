-- 280: official_gazette_items, 8 Oct 2026.
--
-- The Terraqui / LIFE DPP-TEX client source ledger listed BOE (Spanish official gazette) and
-- DOGC (Catalan) as "NOT INGESTED: a gap". They are where a Spanish textile and footwear
-- Royal Decree, or a Catalan waste and circular-economy rule, first becomes binding, so a
-- quiet DPP watch was UNPROVEN for exactly those two places. One table for both gazettes,
-- keeping only items inside the client's remit (services/scrapers/official_gazettes.py);
-- how many items were SCANNED is recorded in sync_runs, so "matched nothing" and "read
-- nothing" stay distinguishable.
--
-- Structure copies the closest precedent (tris_notifications, migration 038): own table per
-- source, the first_seen / last_updated / scraped_at trio, RLS on. Public-read because the
-- rows are published official-gazette titles; writes are service-role only.

CREATE TABLE IF NOT EXISTS public.official_gazette_items (
    id            BIGSERIAL PRIMARY KEY,
    gazette       TEXT NOT NULL CHECK (gazette IN ('boe', 'dogc')),
    identifier    TEXT NOT NULL,                 -- BOE-A-2026-20910, or the DOGC control number
    published_date DATE NOT NULL,
    title         TEXT NOT NULL,
    title_es      TEXT,                          -- DOGC norms carry a Spanish title as well
    section       TEXT,                          -- BOE section code (1, 2A, 2B, 3, 5A, 5B); '1' for DOGC
    department    TEXT,
    rank          TEXT,                          -- BOE epigraph, or DOGC rank (Llei, Decret, Ordre)
    url           TEXT,
    pdf_url       TEXT,
    match_tier    TEXT NOT NULL CHECK (match_tier IN ('strict', 'broad')),
    matched_terms TEXT[] NOT NULL DEFAULT '{}',
    is_test       BOOLEAN NOT NULL DEFAULT FALSE,
    scraped_at    TIMESTAMP DEFAULT NOW(),
    first_seen    TIMESTAMP NOT NULL DEFAULT NOW(),
    last_updated  TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT official_gazette_items_uniq UNIQUE (gazette, identifier)
);

CREATE INDEX IF NOT EXISTS ix_official_gazette_published ON public.official_gazette_items (gazette, published_date DESC);
CREATE INDEX IF NOT EXISTS ix_official_gazette_tier ON public.official_gazette_items (match_tier, published_date DESC);

ALTER TABLE public.official_gazette_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS official_gazette_items_read ON public.official_gazette_items;
CREATE POLICY official_gazette_items_read ON public.official_gazette_items
    FOR SELECT TO anon, authenticated USING (true);
DROP POLICY IF EXISTS official_gazette_items_service_all ON public.official_gazette_items;
CREATE POLICY official_gazette_items_service_all ON public.official_gazette_items
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Data API grants are explicit (the default grant was removed 30 Oct 2026): public-read,
-- service-role write. REVOKE first: on a table created today Supabase's default privileges
-- still hand anon and authenticated every privilege (RLS would block the writes, but the
-- template says SELECT only, and a replay on a stricter project must end in the same state).
REVOKE ALL ON public.official_gazette_items FROM anon, authenticated;
GRANT SELECT ON public.official_gazette_items TO anon, authenticated;
GRANT ALL ON public.official_gazette_items TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.official_gazette_items_id_seq TO service_role;
