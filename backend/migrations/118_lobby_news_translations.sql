-- 118_lobby_news_translations.sql
-- Foreign-language Brussels-lobby news items translated into Brubru's 6 canonical
-- languages (en/es/ca/fr/it/nl) + an extracted card image.
--
-- ~16% of brussels_lobby_news_items are published in a non-canonical language
-- (de, sv, no, fi, da, pt, tr, uk, cs, ...). We detect each item's language and,
-- for the foreign ones, translate title+summary into all 6 up front (local OSS
-- m2m100_418M, no HF credits needed) so any user sees them in their UI language.
-- Images are best-effort og:image, extracted during the same backfill.

-- 1. Item-level: detected language + extracted card image.
ALTER TABLE brussels_lobby_news_items ADD COLUMN IF NOT EXISTS detected_lang VARCHAR(8);
ALTER TABLE brussels_lobby_news_items ADD COLUMN IF NOT EXISTS image_url TEXT;
CREATE INDEX IF NOT EXISTS idx_blni_detected_lang ON brussels_lobby_news_items (detected_lang);

-- 2. Translation cache (one row per item per target language).
CREATE TABLE IF NOT EXISTS brussels_lobby_news_translations (
    id            BIGSERIAL PRIMARY KEY,
    news_item_id  BIGINT NOT NULL REFERENCES brussels_lobby_news_items(id) ON DELETE CASCADE,
    lang          VARCHAR(5) NOT NULL,           -- en / es / ca / fr / it / nl
    title         TEXT,
    summary       TEXT,
    engine        VARCHAR(40),                   -- e.g. m2m100_418M
    translated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (news_item_id, lang)
);
CREATE INDEX IF NOT EXISTS idx_blnt_item_lang ON brussels_lobby_news_translations (news_item_id, lang);

-- 3. Supabase Data API: RLS + public-read + grants (mandatory on new public.* tables).
ALTER TABLE brussels_lobby_news_translations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS blnt_public_read ON brussels_lobby_news_translations;
CREATE POLICY blnt_public_read ON brussels_lobby_news_translations
    FOR SELECT TO anon, authenticated USING (true);

GRANT SELECT ON brussels_lobby_news_translations TO anon, authenticated;
GRANT ALL ON brussels_lobby_news_translations TO service_role;
GRANT USAGE, SELECT ON SEQUENCE brussels_lobby_news_translations_id_seq TO service_role;
