-- Migration 101 — EU institutional news items (MEUB Section 3 "News")
--
-- Aggregates news / publications / stories from the Commission hub + every DG &
-- executive-agency newsroom (the ~85 URLs in docs/new_format/prompt_new_format.md
-- lines 133-381) into one image-rich, PI-filterable feed. Same ECL "content item"
-- markup as the DG events; tagged institution=COMMISSION + commission_dg so it's
-- filterable by department and by the user's Policy Interests, like the rest of
-- MEUB. Also the structured backing store for the /news skill.
--
-- Public reference data: anon + authenticated SELECT, service_role ALL.
-- Safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS eu_news_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_key       TEXT NOT NULL UNIQUE,        -- '<source_key>:<external_id>'

    title           TEXT NOT NULL,
    summary         TEXT,
    news_date       DATE,

    institution     TEXT,                         -- 'COMMISSION', 'EP', ...
    commission_dg   TEXT,                         -- canonical DG code (PI/dept join key)
    item_type       TEXT,                         -- 'news' | 'publication' | 'story' | 'press' | 'other'
    source_key      TEXT,                         -- DG / agency code for provenance
    policy_areas    TEXT[] DEFAULT '{}',

    image_url       TEXT,                         -- card thumbnail (beautiful feed)
    source_url      TEXT,

    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_eu_news_date ON eu_news_items (news_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS ix_eu_news_dg ON eu_news_items (commission_dg);
CREATE INDEX IF NOT EXISTS ix_eu_news_institution ON eu_news_items (institution);
CREATE INDEX IF NOT EXISTS ix_eu_news_type ON eu_news_items (item_type);

ALTER TABLE eu_news_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS eu_news_public_read ON eu_news_items;
CREATE POLICY eu_news_public_read ON eu_news_items
    FOR SELECT TO anon, authenticated USING (true);

GRANT SELECT ON eu_news_items TO anon, authenticated;
GRANT ALL ON eu_news_items TO service_role;

COMMIT;
