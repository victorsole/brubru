-- 275: oj_entries.language -- the language an entry's title (and act) is in.
--
-- The OJ publishes some acts in one language only: a corrigendum to the Hungarian or
-- Swedish version of a directive has no English version at all (4 of 10 L acts on
-- 7 Oct 2026). sync_oj read EUR-Lex's English daily view, so those acts never reached
-- My OJ. It now reads Cellar by OJ publication date and stores them with their own
-- title; this column says which language that is, so the Catalan pipeline (which
-- translates from English) can skip them instead of failing on them every day.
ALTER TABLE oj_entries ADD COLUMN IF NOT EXISTS language text NOT NULL DEFAULT 'en';
