-- Migration 092: efpia_scraped_items table for the EFPIA pharma/health scraper.
--
-- Driver: 28 May 2026 EFPIA pilot. The daily scraper hits ~80 sources (DG SANTE,
-- EP SANT, EMA, two horizontal EC) and persists every distinct item it finds.
-- The Brubru EFPIA Brief and the /api/efpia/daily-candidates endpoint read
-- from this table.
--
-- Dedup: dedup_hash = sha256(source_id || '|' || item_url). UNIQUE.
-- Each scraper run UPSERTs on dedup_hash, bumping scraped_at + raw_text.
--
-- Source catalogue lives in backend/data/efpia_brief/sources.json (no FK in
-- the DB, sources.json is the authoritative registry).

CREATE TABLE IF NOT EXISTS efpia_scraped_items (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id         VARCHAR(64) NOT NULL,
    institution       VARCHAR(16) NOT NULL,
    bucket            VARCHAR(32) NOT NULL,
    kind              VARCHAR(48) NOT NULL,
    item_url          TEXT        NOT NULL,
    item_title        TEXT        NOT NULL,
    item_summary      TEXT,
    item_published_at TIMESTAMPTZ,
    scraped_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    relevance_score   SMALLINT    NOT NULL DEFAULT 50,
    raw_text          TEXT,
    dedup_hash        VARCHAR(64) NOT NULL,
    metadata          JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_efpia_scraped_items_dedup_hash UNIQUE (dedup_hash)
);

CREATE INDEX IF NOT EXISTS idx_efpia_scraped_scraped_at_desc
    ON efpia_scraped_items (scraped_at DESC);

CREATE INDEX IF NOT EXISTS idx_efpia_scraped_relevance_scraped
    ON efpia_scraped_items (relevance_score DESC, scraped_at DESC);

CREATE INDEX IF NOT EXISTS idx_efpia_scraped_institution_scraped
    ON efpia_scraped_items (institution, scraped_at DESC);

CREATE INDEX IF NOT EXISTS idx_efpia_scraped_source_scraped
    ON efpia_scraped_items (source_id, scraped_at DESC);

CREATE INDEX IF NOT EXISTS idx_efpia_scraped_published_at_desc
    ON efpia_scraped_items (item_published_at DESC NULLS LAST);

-- Supabase Data API grants per memory/feedback_supabase_data_api_grants.md.
-- Only authenticated + service_role; this table is tenant-internal, not for
-- the anon public stream.
GRANT SELECT ON efpia_scraped_items TO authenticated;
GRANT ALL    ON efpia_scraped_items TO service_role;
