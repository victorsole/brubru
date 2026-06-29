-- 193_social_accounts.sql
-- Phase 4, Wave 0 (28 Jun 2026) — social account directory foundations.
--
-- Two tables:
--   social_platforms  reference table; a new platform = one INSERT, NOT a migration
--                     (so the set is never a rigid enum). Also encodes the D1 content-fetch
--                     feasibility tier per platform.
--   social_accounts   polymorphic (entity_type, entity_key) mapping of EU entities to their
--                     accounts across all platforms. Account MAPPING only (Phase 4.1);
--                     content fetching (4.2) is gated per-account by content_fetch_enabled.
--
-- Public-read reference data (Brubru surfaces read it), service_role writes -> public-read
-- Supabase grant pattern.

-- ---------------------------------------------------------------- social_platforms
CREATE TABLE IF NOT EXISTS public.social_platforms (
    code        TEXT PRIMARY KEY,                       -- 'x', 'linkedin', 'mastodon', ...
    name        TEXT NOT NULL,
    fetch_tier  TEXT NOT NULL DEFAULT 'none'            -- open | gated | hard | none
                CHECK (fetch_tier IN ('open', 'gated', 'hard', 'none')),
    notes       TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- fetch_tier: open = clean public API; gated = API exists but approval/quota/paywall;
-- hard = no usable API + anti-scrape + ToS; none = no read path (yet).
INSERT INTO public.social_platforms (code, name, fetch_tier, notes) VALUES
    ('x',         'X (Twitter)',        'hard',  'paid API tiers; scraping breaches ToS + anti-bot'),
    ('instagram', 'Instagram',          'hard',  'Graph API only for owned business accounts'),
    ('linkedin',  'LinkedIn',           'hard',  'most hostile; official API near-useless for monitoring'),
    ('tiktok',    'TikTok',             'gated', 'Research API exists but gated/approval'),
    ('threads',   'Threads',            'hard',  'no public read API'),
    ('facebook',  'Facebook',           'gated', 'Graph API limited to owned pages'),
    ('mastodon',  'Mastodon (EU Voice)','open',  'open ActivityPub/REST API'),
    ('bluesky',   'Bluesky',            'open',  'open AT-protocol API'),
    ('youtube',   'YouTube',            'open',  'Data API, free quota'),
    ('flickr',    'Flickr',             'open',  'open API'),
    ('spotify',   'Spotify',            'open',  'Web API'),
    ('reddit',    'Reddit',             'gated', 'API now rate-limited/paid'),
    ('pinterest', 'Pinterest',          'gated', 'API requires app approval'),
    ('whatsapp',  'WhatsApp Channels',  'none',  'broadcast channels, no read API'),
    ('wsocial',   'WSocial (wsocial.news)','none','emerging; no important EU accounts yet, tracked for momentum')
ON CONFLICT (code) DO NOTHING;

-- ---------------------------------------------------------------- social_accounts
CREATE TABLE IF NOT EXISTS public.social_accounts (
    id                   BIGSERIAL PRIMARY KEY,
    entity_type          TEXT NOT NULL,    -- institution|ec_dg|ep_committee|political_group|
                                           -- eu_agency|perm_rep|eutr_org|mep|commissioner|
                                           -- ec_official|eu_influencer
    entity_key           TEXT NOT NULL,    -- natural id in the source table (EUTR id, committee
                                           -- code, MEP id, group code, ...)
    entity_name          TEXT,             -- denormalised display name (audit convenience)

    platform             TEXT NOT NULL REFERENCES public.social_platforms(code),
    scope                TEXT NOT NULL DEFAULT 'central',  -- central|country:DE|language:fr|topic:..|office:..
    handle               TEXT,
    account_url          TEXT NOT NULL,    -- canonical URL; the dedup key
    platform_account_id  TEXT,             -- stable id (e.g. YouTube channel id)

    status               TEXT NOT NULL DEFAULT 'candidate'
                         CHECK (status IN ('candidate', 'verified', 'rejected', 'dormant')),
    verified             BOOLEAN NOT NULL DEFAULT false,
    verification_source  TEXT,
    discovery_source     TEXT NOT NULL,    -- wikidata|eu_directory|ep_page|official_site|eutr|manual
    confidence           REAL,

    follower_count       BIGINT,
    content_fetch_enabled BOOLEAN NOT NULL DEFAULT false,  -- per-account 4.2 switch (off by default)

    extra                JSONB NOT NULL DEFAULT '{}'::jsonb,
    first_seen_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_checked_at      TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT social_accounts_url_uq UNIQUE (account_url)
);

CREATE INDEX IF NOT EXISTS idx_social_accounts_entity
    ON public.social_accounts (entity_type, entity_key);
CREATE INDEX IF NOT EXISTS idx_social_accounts_platform
    ON public.social_accounts (platform);
CREATE INDEX IF NOT EXISTS idx_social_accounts_status
    ON public.social_accounts (status);

-- ---------------------------------------------------------------- RLS + grants (public-read)
ALTER TABLE public.social_platforms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.social_accounts  ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "social_platforms_anon_read" ON public.social_platforms;
CREATE POLICY "social_platforms_anon_read" ON public.social_platforms FOR SELECT TO anon USING (true);
DROP POLICY IF EXISTS "social_platforms_auth_read" ON public.social_platforms;
CREATE POLICY "social_platforms_auth_read" ON public.social_platforms FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS "social_platforms_service_all" ON public.social_platforms;
CREATE POLICY "social_platforms_service_all" ON public.social_platforms FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "social_accounts_anon_read" ON public.social_accounts;
CREATE POLICY "social_accounts_anon_read" ON public.social_accounts FOR SELECT TO anon USING (true);
DROP POLICY IF EXISTS "social_accounts_auth_read" ON public.social_accounts;
CREATE POLICY "social_accounts_auth_read" ON public.social_accounts FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS "social_accounts_service_all" ON public.social_accounts;
CREATE POLICY "social_accounts_service_all" ON public.social_accounts FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Supabase Data API grants (mandatory; default grant removed 30 Oct 2026)
GRANT SELECT ON public.social_platforms TO anon;
GRANT SELECT ON public.social_platforms TO authenticated;
GRANT ALL ON public.social_platforms TO service_role;

GRANT SELECT ON public.social_accounts TO anon;
GRANT SELECT ON public.social_accounts TO authenticated;
GRANT ALL ON public.social_accounts TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.social_accounts_id_seq TO service_role;
