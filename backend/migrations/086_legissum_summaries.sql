-- Migration 086: legissum_summaries — the "Summaries of EU legislation" catalogue.
--
-- LEGISSUM is NOT in the Cellar SPARQL graph (only study/evaluation executive
-- summaries are). The plain-language legislative summaries live behind the
-- WAF-walled eur-lex.europa.eu/browse/summaries tree and are harvested by
-- services/scrapers/legissum_scraper.py (Playwright) into this table. Powers
-- /api/v2/legislative/eur-lex/laws/summaries[/ {id}].
--
-- Public-read reference data. Mandatory Data-API order:
-- CREATE -> ENABLE RLS -> POLICY -> GRANT (see CLAUDE.md).

CREATE TABLE IF NOT EXISTS public.legissum_summaries (
    slug             TEXT PRIMARY KEY,
    title            TEXT NOT NULL,
    chapter_code     TEXT,
    chapter_title    TEXT,
    url              TEXT NOT NULL,
    celex            TEXT,
    summary_text     TEXT,
    summary_html     TEXT,
    text_fetched_at  TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.legissum_summaries IS
  'LEGISSUM "Summaries of EU legislation" catalogue, harvested from EUR-Lex via Playwright. Safe to re-sync.';

CREATE INDEX IF NOT EXISTS legissum_chapter_idx ON public.legissum_summaries (chapter_code);
CREATE INDEX IF NOT EXISTS legissum_celex_idx ON public.legissum_summaries (celex);
CREATE INDEX IF NOT EXISTS legissum_title_lower_idx ON public.legissum_summaries (LOWER(title));

ALTER TABLE public.legissum_summaries ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS legissum_public_read ON public.legissum_summaries;
CREATE POLICY legissum_public_read ON public.legissum_summaries
    FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS legissum_service_all ON public.legissum_summaries;
CREATE POLICY legissum_service_all ON public.legissum_summaries
    FOR ALL TO service_role USING (true) WITH CHECK (true);

GRANT SELECT ON public.legissum_summaries TO anon, authenticated;
GRANT ALL    ON public.legissum_summaries TO service_role;
