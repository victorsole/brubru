-- 223_catalan_translations_oj_id.sql
-- Let the Catalan corpus hold OJ C-series items, not only CELEX-keyed acts.
--
-- WHY. My OJ links a card to its full Catalan text via api/oj.py, which matches
-- oj_entries.celex against catalan_translations.celex. That works for L-series
-- (82.9% carry a CELEX) but NEVER for C-series: oj_scraper.derive_celex()
-- returns None for anything that is not L by design, so all 1,614 C rows have
-- celex IS NULL and can never acquire a Catalan link. C-series is the bulk of
-- daily OJ volume (26 of 27 entries on 26 Aug 2026), so "the whole OJ in
-- Catalan" is unreachable while the corpus is CELEX-only.
--
-- Every C entry does carry a stable oj_id ('C_202604005'), and EUR-Lex serves
-- the full text straight from it (OJ:C_202604005) with no CELEX needed. So the
-- corpus gains oj_id as an ALTERNATIVE key rather than overloading celex with
-- values that are not CELEXes -- this table is the source of truth for the
-- public corpus, and 1,614 mislabelled rows would mislead every later reader.
--
-- celex therefore has to lose NOT NULL. Its UNIQUE index is kept: Postgres
-- allows many NULLs in a unique index, so L-series uniqueness is unaffected.
-- A CHECK guarantees a row is still addressable by exactly one of the two keys.

BEGIN;

ALTER TABLE public.catalan_translations
    ADD COLUMN IF NOT EXISTS oj_id VARCHAR(32);

COMMENT ON COLUMN public.catalan_translations.oj_id IS
    'OJ C-series identifier (e.g. C_202604005) for corpus pages that have no '
    'CELEX. Mutually exclusive with celex -- see catalan_translations_key_ck.';

-- C-series rows have no CELEX at all.
ALTER TABLE public.catalan_translations
    ALTER COLUMN celex DROP NOT NULL;

-- One page per OJ id. Partial so the existing CELEX-keyed rows (oj_id NULL)
-- are not forced into it.
CREATE UNIQUE INDEX IF NOT EXISTS ix_catalan_translations_oj_id
    ON public.catalan_translations (oj_id)
    WHERE oj_id IS NOT NULL;

-- A page must be reachable by exactly one key, never zero and never both:
-- both would make the /legislacio-ue-catala/<key>/ slug ambiguous.
ALTER TABLE public.catalan_translations
    DROP CONSTRAINT IF EXISTS catalan_translations_key_ck;
ALTER TABLE public.catalan_translations
    ADD CONSTRAINT catalan_translations_key_ck
    CHECK (num_nonnulls(celex, oj_id) = 1);

COMMIT;

-- Data API grants: catalan_translations already exists and is public-read, so
-- the table's grants and RLS policy are unchanged by adding a column. Re-issued
-- here so a replay of this file on a fresh environment (staging spin-up,
-- restore) still lands them -- the default grant was removed 30 Oct 2026.
GRANT SELECT ON public.catalan_translations TO anon, authenticated;
GRANT ALL    ON public.catalan_translations TO service_role;
