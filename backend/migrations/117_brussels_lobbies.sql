-- Migration 117 — Brussels lobbies (API v2 proprietary "Brussels lobbies")
--
-- Brubru-proprietary product: a single ranked feed of what every Brussels-based
-- EU Transparency Register organisation is publishing. Nobody else aggregates
-- this. Derived from `eu_transparency_register` (the official daily XML dump)
-- enriched with per-org news detection (RSS / Atom autodiscovery, sitemap
-- lastmod, validated path probe with a soft-404 guard, Tavily/Playwright
-- fallback for bot-blocked sites).
--
--   brussels_lobby_profiles    — one row per Brussels org: normalised org type,
--                                news-availability flags, latest-item date, the
--                                profile body (5-datapoint contract).
--   brussels_lobby_news_items  — dated news/update items per org.
--
-- "Brussels-based" = EU office OR head office in Brussels/Bruxelles. org_type is
-- the public-facing normalisation of registration_category; eutr_section is the
-- official EUTR section (I–VI); for_profit is derived from the category.
--
-- Public reference data: anon + authenticated SELECT, service_role ALL.
-- Re-runnable.

BEGIN;

CREATE TABLE IF NOT EXISTS brussels_lobby_profiles (
    id                    BIGSERIAL PRIMARY KEY,
    identification_code   VARCHAR(40) NOT NULL UNIQUE
        REFERENCES eu_transparency_register (identification_code) ON DELETE CASCADE,

    -- Identity (mirrored from the register for fast directory queries)
    original_name         TEXT,
    acronym               TEXT,
    registration_category TEXT,                 -- raw EUTR category

    -- Classification (the public-facing type taxonomy)
    org_type              VARCHAR(24),          -- ngo | trade_association | company | think_tank | consultancy | law_firm | trade_union | academic | religious | public_authority | third_country | self_employed | other
    eutr_section          VARCHAR(4),           -- I | II | III | IV | V | VI
    for_profit            BOOLEAN,
    is_global_corp        BOOLEAN DEFAULT false, -- multinational w/ global (non-EU-affairs) newsroom

    -- Why it is Brussels-based
    office_basis          VARCHAR(12),          -- eu_office | head_office | both
    head_office_city      TEXT,
    head_office_country   TEXT,

    website_url           TEXT,

    -- News availability
    news_status           VARCHAR(12) NOT NULL DEFAULT 'unknown',  -- active | none | error | blocked | unknown
    news_source_kind      VARCHAR(12),          -- rss | atom | sitemap | html | none
    news_feed_url         TEXT,                 -- discovered feed / news-index URL
    last_item_date        TIMESTAMPTZ,
    item_count            INTEGER NOT NULL DEFAULT 0,

    -- The three requested flags
    has_org_data          BOOLEAN NOT NULL DEFAULT true,   -- register data (always true here)
    has_news_data         BOOLEAN NOT NULL DEFAULT false,  -- at least one news item

    -- Influence signals (for ranking / filtering)
    ep_accredited_number  INTEGER,
    members_fte           NUMERIC,
    costs_max             NUMERIC,
    interests             TEXT[] DEFAULT ARRAY[]::TEXT[],

    -- 5-datapoint contract
    public_url            TEXT,                 -- register detail page
    body_txt              TEXT,
    body_html             TEXT,

    last_checked_at       TIMESTAMPTZ,          -- when news detection last ran
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_blp_org_type    ON brussels_lobby_profiles (org_type);
CREATE INDEX IF NOT EXISTS ix_blp_section      ON brussels_lobby_profiles (eutr_section);
CREATE INDEX IF NOT EXISTS ix_blp_has_news     ON brussels_lobby_profiles (has_news_data);
CREATE INDEX IF NOT EXISTS ix_blp_last_item    ON brussels_lobby_profiles (last_item_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS ix_blp_costs        ON brussels_lobby_profiles (costs_max DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS ix_blp_interests    ON brussels_lobby_profiles USING gin (interests);
CREATE INDEX IF NOT EXISTS ix_blp_name_search  ON brussels_lobby_profiles
    USING gin (to_tsvector('english', COALESCE(original_name,'') || ' ' || COALESCE(acronym,'')));

CREATE TABLE IF NOT EXISTS brussels_lobby_news_items (
    id                   BIGSERIAL PRIMARY KEY,
    identification_code  VARCHAR(40) NOT NULL
        REFERENCES eu_transparency_register (identification_code) ON DELETE CASCADE,
    guid                 TEXT NOT NULL,         -- rss guid or canonical item URL (dedup key)
    item_url             TEXT,
    title                TEXT,
    summary              TEXT,
    published_at         TIMESTAMPTZ,
    source_kind          VARCHAR(12),           -- rss | atom | sitemap | html

    -- 5-datapoint contract (per item)
    public_url           TEXT,
    body_txt             TEXT,
    body_html            TEXT,

    fetched_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (identification_code, guid)
);

CREATE INDEX IF NOT EXISTS ix_blni_code      ON brussels_lobby_news_items (identification_code);
CREATE INDEX IF NOT EXISTS ix_blni_published ON brussels_lobby_news_items (published_at DESC NULLS LAST);

ALTER TABLE brussels_lobby_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE brussels_lobby_news_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS blp_public_read ON brussels_lobby_profiles;
CREATE POLICY blp_public_read ON brussels_lobby_profiles
    FOR SELECT TO anon, authenticated USING (true);
DROP POLICY IF EXISTS blni_public_read ON brussels_lobby_news_items;
CREATE POLICY blni_public_read ON brussels_lobby_news_items
    FOR SELECT TO anon, authenticated USING (true);

GRANT SELECT ON brussels_lobby_profiles TO anon, authenticated;
GRANT ALL ON brussels_lobby_profiles TO service_role;
GRANT USAGE, SELECT ON SEQUENCE brussels_lobby_profiles_id_seq TO service_role;
GRANT SELECT ON brussels_lobby_news_items TO anon, authenticated;
GRANT ALL ON brussels_lobby_news_items TO service_role;
GRANT USAGE, SELECT ON SEQUENCE brussels_lobby_news_items_id_seq TO service_role;

COMMENT ON TABLE brussels_lobby_profiles IS
    'Brubru-proprietary directory of Brussels-based EU Transparency Register orgs '
    'with per-org news availability. Backs /api/v2/proprietary/brussels-lobbies.';
COMMENT ON TABLE brussels_lobby_news_items IS
    'Dated news/update items scraped from Brussels lobby websites. Backs '
    '/api/v2/proprietary/brussels-lobbies/{id}/news.';

COMMIT;
