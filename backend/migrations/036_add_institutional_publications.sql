-- Institutional publications ingested by the generic RSS ingester.
-- Unified shape across all ~80 EU institutional feeds (feeds.ec.europa.eu,
-- EUR-Lex OJ RSS, decentralised agencies, EEAS, ECB, etc.). Consumed internally
-- by chatbot/Bubble and externally via /api/v1/publications.
--
-- Separate from rss_feeds/rss_entries (which back the per-user My EU Bubble
-- feature with different semantics).

CREATE TABLE IF NOT EXISTS institutional_publications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_slug         VARCHAR(100) NOT NULL,       -- matches YAML config filename, e.g. "ec_press", "ecb_press", "ema_news"
    institution_slug    VARCHAR(100) NOT NULL,       -- classified institution, e.g. "european_commission", "ema", "ecb"
    category            VARCHAR(50),                  -- press_release | legislation | report | speech | agenda | consultation | other

    external_id         VARCHAR(500) NOT NULL,       -- stable id from the feed (entry.id or entry.link fallback)
    url                 TEXT NOT NULL,
    title               TEXT NOT NULL,
    summary             TEXT,
    html_content        TEXT,                         -- if full content fetched
    language            VARCHAR(10) DEFAULT 'en',

    published_date      TIMESTAMPTZ,
    updated_date        TIMESTAMPTZ,

    policy_areas        TEXT[] DEFAULT '{}',
    tags                TEXT[] DEFAULT '{}',
    authors             TEXT[] DEFAULT '{}',
    extra_metadata      JSONB DEFAULT '{}'::jsonb,   -- feed-specific extras

    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT institutional_publications_external_id_unique UNIQUE (source_slug, external_id)
);

CREATE INDEX IF NOT EXISTS idx_inst_pub_institution      ON institutional_publications (institution_slug);
CREATE INDEX IF NOT EXISTS idx_inst_pub_source           ON institutional_publications (source_slug);
CREATE INDEX IF NOT EXISTS idx_inst_pub_published_date   ON institutional_publications (published_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_inst_pub_category         ON institutional_publications (category);

-- Full-text search on title + summary
CREATE INDEX IF NOT EXISTS idx_inst_pub_fts ON institutional_publications
    USING GIN (to_tsvector('simple', COALESCE(title, '') || ' ' || COALESCE(summary, '')));

-- RLS: service-only reads (same posture as api_keys)
ALTER TABLE institutional_publications ENABLE ROW LEVEL SECURITY;
