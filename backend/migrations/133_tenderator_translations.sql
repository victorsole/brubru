-- Migration 133: translation layer for the Tenderator's 5 sources.
-- Mirrors the MEUB-news pattern (migration 118 / brussels_lobby_news_translations):
-- pre-compute-and-cache, no on-the-fly translation, one sidecar per source.
--
-- Brubru renders the Tenderator in 6 languages (en / es / ca / fr / it / nl).
-- ~22% of TED titles + ~57% of F&T-calls-for-tenders titles are in languages
-- OUTSIDE the 6 (PL / DE / CS / PT / BG / SV / FI etc.). For those rows we
-- translate title + description into all 6 up front via a CPU-local M2M100
-- backfill so any user sees them in their UI language. Items already in one
-- of the 6 stay as-is (the read path falls back to the original).
--
-- All 5 sidecars carry the mandatory Supabase Data API grants (anon +
-- authenticated SELECT, service_role ALL) per the data-API-grants rule.

-- 1. detected_lang columns on the 5 source tables --------------------------- --
ALTER TABLE tenders                ADD COLUMN IF NOT EXISTS detected_lang VARCHAR(8);
ALTER TABLE ft_calls_for_proposals ADD COLUMN IF NOT EXISTS detected_lang VARCHAR(8);
ALTER TABLE ft_calls_for_tenders   ADD COLUMN IF NOT EXISTS detected_lang VARCHAR(8);
ALTER TABLE ft_funded_projects     ADD COLUMN IF NOT EXISTS detected_lang VARCHAR(8);
ALTER TABLE economy_items          ADD COLUMN IF NOT EXISTS detected_lang VARCHAR(8);

CREATE INDEX IF NOT EXISTS idx_tenders_detected_lang                ON tenders                (detected_lang);
CREATE INDEX IF NOT EXISTS idx_ft_calls_for_proposals_detected_lang ON ft_calls_for_proposals (detected_lang);
CREATE INDEX IF NOT EXISTS idx_ft_calls_for_tenders_detected_lang   ON ft_calls_for_tenders   (detected_lang);
CREATE INDEX IF NOT EXISTS idx_ft_funded_projects_detected_lang     ON ft_funded_projects     (detected_lang);
CREATE INDEX IF NOT EXISTS idx_economy_items_detected_lang          ON economy_items          (detected_lang);

-- 2. One sidecar per source ------------------------------------------------- --
-- The id type matches each source's PK type. UNIQUE(item, lang) makes the
-- backfill idempotent via ON CONFLICT DO UPDATE.

CREATE TABLE IF NOT EXISTS tenders_translations (
    id            BIGSERIAL PRIMARY KEY,
    tender_id     INTEGER NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    lang          VARCHAR(5) NOT NULL,
    title         TEXT,
    summary       TEXT,
    engine        VARCHAR(40),
    translated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tender_id, lang)
);
CREATE INDEX IF NOT EXISTS idx_tenders_translations_item_lang ON tenders_translations (tender_id, lang);

CREATE TABLE IF NOT EXISTS ft_calls_for_proposals_translations (
    id            BIGSERIAL PRIMARY KEY,
    call_id       UUID NOT NULL REFERENCES ft_calls_for_proposals(id) ON DELETE CASCADE,
    lang          VARCHAR(5) NOT NULL,
    title         TEXT,
    summary       TEXT,
    engine        VARCHAR(40),
    translated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (call_id, lang)
);
CREATE INDEX IF NOT EXISTS idx_ft_calls_for_proposals_translations_item_lang
    ON ft_calls_for_proposals_translations (call_id, lang);

CREATE TABLE IF NOT EXISTS ft_calls_for_tenders_translations (
    id            BIGSERIAL PRIMARY KEY,
    tender_uuid   UUID NOT NULL REFERENCES ft_calls_for_tenders(id) ON DELETE CASCADE,
    lang          VARCHAR(5) NOT NULL,
    title         TEXT,
    summary       TEXT,
    engine        VARCHAR(40),
    translated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tender_uuid, lang)
);
CREATE INDEX IF NOT EXISTS idx_ft_calls_for_tenders_translations_item_lang
    ON ft_calls_for_tenders_translations (tender_uuid, lang);

CREATE TABLE IF NOT EXISTS ft_funded_projects_translations (
    id            BIGSERIAL PRIMARY KEY,
    project_uuid  UUID NOT NULL REFERENCES ft_funded_projects(id) ON DELETE CASCADE,
    lang          VARCHAR(5) NOT NULL,
    title         TEXT,
    summary       TEXT,
    engine        VARCHAR(40),
    translated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_uuid, lang)
);
CREATE INDEX IF NOT EXISTS idx_ft_funded_projects_translations_item_lang
    ON ft_funded_projects_translations (project_uuid, lang);

CREATE TABLE IF NOT EXISTS economy_items_translations (
    id            BIGSERIAL PRIMARY KEY,
    item_id       INTEGER NOT NULL REFERENCES economy_items(id) ON DELETE CASCADE,
    lang          VARCHAR(5) NOT NULL,
    title         TEXT,
    summary       TEXT,
    engine        VARCHAR(40),
    translated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (item_id, lang)
);
CREATE INDEX IF NOT EXISTS idx_economy_items_translations_item_lang
    ON economy_items_translations (item_id, lang);

-- 3. Supabase Data API grants (anon + authenticated SELECT, service_role ALL) ---

ALTER TABLE tenders_translations                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE ft_calls_for_proposals_translations   ENABLE ROW LEVEL SECURITY;
ALTER TABLE ft_calls_for_tenders_translations     ENABLE ROW LEVEL SECURITY;
ALTER TABLE ft_funded_projects_translations       ENABLE ROW LEVEL SECURITY;
ALTER TABLE economy_items_translations            ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenders_translations_public_read ON tenders_translations;
CREATE POLICY tenders_translations_public_read ON tenders_translations
    FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS ft_calls_for_proposals_translations_public_read ON ft_calls_for_proposals_translations;
CREATE POLICY ft_calls_for_proposals_translations_public_read ON ft_calls_for_proposals_translations
    FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS ft_calls_for_tenders_translations_public_read ON ft_calls_for_tenders_translations;
CREATE POLICY ft_calls_for_tenders_translations_public_read ON ft_calls_for_tenders_translations
    FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS ft_funded_projects_translations_public_read ON ft_funded_projects_translations;
CREATE POLICY ft_funded_projects_translations_public_read ON ft_funded_projects_translations
    FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS economy_items_translations_public_read ON economy_items_translations;
CREATE POLICY economy_items_translations_public_read ON economy_items_translations
    FOR SELECT TO anon, authenticated USING (true);

GRANT SELECT ON tenders_translations                 TO anon, authenticated;
GRANT SELECT ON ft_calls_for_proposals_translations  TO anon, authenticated;
GRANT SELECT ON ft_calls_for_tenders_translations    TO anon, authenticated;
GRANT SELECT ON ft_funded_projects_translations      TO anon, authenticated;
GRANT SELECT ON economy_items_translations           TO anon, authenticated;

GRANT ALL ON tenders_translations                    TO service_role;
GRANT ALL ON ft_calls_for_proposals_translations     TO service_role;
GRANT ALL ON ft_calls_for_tenders_translations       TO service_role;
GRANT ALL ON ft_funded_projects_translations         TO service_role;
GRANT ALL ON economy_items_translations              TO service_role;

GRANT USAGE, SELECT ON SEQUENCE tenders_translations_id_seq                TO service_role;
GRANT USAGE, SELECT ON SEQUENCE ft_calls_for_proposals_translations_id_seq TO service_role;
GRANT USAGE, SELECT ON SEQUENCE ft_calls_for_tenders_translations_id_seq   TO service_role;
GRANT USAGE, SELECT ON SEQUENCE ft_funded_projects_translations_id_seq     TO service_role;
GRANT USAGE, SELECT ON SEQUENCE economy_items_translations_id_seq          TO service_role;
