-- 195_social_posts.sql
-- Phase 4.2 — open-tier content layer. Recent posts fetched from the mapped social accounts
-- via public, keyless, ToS-clean APIs (Bluesky AppView, Mastodon REST, YouTube channel RSS).
-- Hard platforms (X/Instagram/LinkedIn/TikTok) are NOT fetched (D1: no paid API, no covert
-- scraping) so they never produce rows here. Public-read reference data, service_role writes.

CREATE TABLE IF NOT EXISTS public.social_posts (
    id                  BIGSERIAL PRIMARY KEY,
    account_id          BIGINT NOT NULL REFERENCES public.social_accounts(id) ON DELETE CASCADE,
    platform            TEXT NOT NULL REFERENCES public.social_platforms(code),
    platform_post_id    TEXT NOT NULL,          -- native id/uri (dedup within an account)
    post_url            TEXT,                   -- permalink
    content             TEXT,                   -- text (or video title for YouTube)
    lang                TEXT,
    posted_at           TIMESTAMPTZ,
    like_count          BIGINT,
    repost_count        BIGINT,                 -- reposts / boosts
    reply_count         BIGINT,
    view_count          BIGINT,
    media               JSONB NOT NULL DEFAULT '[]'::jsonb,
    extra               JSONB NOT NULL DEFAULT '{}'::jsonb,
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT social_posts_account_post_uq UNIQUE (account_id, platform_post_id)
);

CREATE INDEX IF NOT EXISTS idx_social_posts_account ON public.social_posts (account_id);
CREATE INDEX IF NOT EXISTS idx_social_posts_posted ON public.social_posts (posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_social_posts_platform ON public.social_posts (platform);

ALTER TABLE public.social_posts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "social_posts_anon_read" ON public.social_posts;
CREATE POLICY "social_posts_anon_read" ON public.social_posts FOR SELECT TO anon USING (true);
DROP POLICY IF EXISTS "social_posts_auth_read" ON public.social_posts;
CREATE POLICY "social_posts_auth_read" ON public.social_posts FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS "social_posts_service_all" ON public.social_posts;
CREATE POLICY "social_posts_service_all" ON public.social_posts FOR ALL TO service_role USING (true) WITH CHECK (true);

GRANT SELECT ON public.social_posts TO anon;
GRANT SELECT ON public.social_posts TO authenticated;
GRANT ALL ON public.social_posts TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.social_posts_id_seq TO service_role;
