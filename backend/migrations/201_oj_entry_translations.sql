-- 201_oj_entry_translations.sql
-- Per-language translations of Official Journal entries (MEUB "My OJ").
--
-- oj_entries carries a single English title + plain_explanation. Catalan (and
-- later other) users should read each day's OJ in their UI language, so we cache
-- one translated row per (entry, target-language), following the proven
-- brussels_lobby_news_translations sidecar pattern (migration 118).
-- Engine: Softcatala NMT eng-cat (local CTranslate2, free) for 'ca'; the lang
-- column leaves room for es/fr/it/nl later without schema change.
-- Backfill: scripts/backfill_oj_translations.py (runs locally against prod DB).

CREATE TABLE IF NOT EXISTS oj_entry_translations (
    id            BIGSERIAL PRIMARY KEY,
    oj_entry_id   UUID NOT NULL REFERENCES oj_entries(id) ON DELETE CASCADE,
    lang          VARCHAR(5) NOT NULL,           -- ca (later: es / fr / it / nl)
    title         TEXT,
    plain_explanation TEXT,
    engine        VARCHAR(40),                   -- e.g. softcatala-eng-cat
    translated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (oj_entry_id, lang)
);
CREATE INDEX IF NOT EXISTS idx_ojet_entry_lang ON oj_entry_translations (oj_entry_id, lang);

-- Supabase Data API: RLS + public-read + grants (mandatory on new public.* tables).
ALTER TABLE oj_entry_translations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ojet_public_read ON oj_entry_translations;
CREATE POLICY ojet_public_read ON oj_entry_translations
    FOR SELECT TO anon, authenticated USING (true);

GRANT SELECT ON oj_entry_translations TO anon, authenticated;
GRANT ALL ON oj_entry_translations TO service_role;
GRANT USAGE, SELECT ON SEQUENCE oj_entry_translations_id_seq TO service_role;
