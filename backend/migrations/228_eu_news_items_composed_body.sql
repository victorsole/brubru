-- 228_eu_news_items_composed_body.sql
--
-- Give `eu_news_items` the three body columns the v2 five-datapoint contract requires.
--
-- Why (measured 8 September 2026)
-- -------------------------------
-- `/api/v2/news/all` unions two stores: `economy_items` (agencies) and `eu_news_items`
-- (Commission, Parliament, Council). The economy half carries `body_txt` / `body_html`
-- as real columns. The institutional half has NO body column at all -- the table holds
-- only `title` and `summary` -- so `_institutional_sql` served:
--
--     n.summary AS body_txt, NULL AS body_html
--
-- Which means, across 10,143 institutional rows:
--   * `body_html` is NULL on EVERY row, 100%.
--   * `body_txt` is NULL or empty on 2,939 rows, 29%, because the upstream feed
--     published no summary.
--
-- Two of the five mandatory datapoints are therefore absent from a whole half of the
-- endpoint's corpus. `feedback_api_endpoint_pattern_contract` is explicit that
-- structured data is NOT exempt: the body is composed at backfill time and
-- `body_source` records how, because the body is what feeds chat and RAG and what
-- makes "code once against the envelope" true.
--
-- What this adds
-- --------------
--   body_txt     composed plain text
--   body_html    composed HTML
--   body_source  HOW the body was produced, so a consumer is never misled about it
--
-- `body_source` is the honesty column and the reason this is safe. These bodies are
-- COMPOSED from the title, the summary and the source link. They are NOT the scraped
-- article: `eu_news_items` never held the article text and this migration does not
-- invent it. A consumer reading `body_source = 'composed:title+summary'` knows exactly
-- what it is holding. Writing a fabricated full text would be what
-- feedback_backfill_no_hallucination forbids; composing a truthful rendering of the
-- fields we DO have is what the contract requires.
--
-- Values written by scripts/backfill_eu_news_bodies.py:
--   'composed:title+summary'  both fields present (7,204 rows)
--   'composed:title'          summary empty; the body is the headline plus provenance
--                             (2,939 rows)
--
-- Nullable, no default
-- --------------------
-- Deliberately nullable with no default: a NULL `body_source` means "not yet
-- composed", which is a state the backfill and any future ingest can detect and act
-- on. A default would make an uncomposed row indistinguishable from a composed one.
-- Compare feedback_zero_denominator_is_not_a_pass: the third state has to exist.
--
-- Grants
-- ------
-- ALTER TABLE only. `public.eu_news_items` already carries its Data API grants and
-- RLS policy, and adding a column does not reset them, so no GRANT is repeated here.
-- (feedback_supabase_data_api_grants applies to CREATE TABLE, not to ALTER.)
--
-- Reversible
-- ----------
--   ALTER TABLE public.eu_news_items
--     DROP COLUMN body_txt, DROP COLUMN body_html, DROP COLUMN body_source;
-- Nothing reads these columns until the api/v2/news change ships, so the migration is
-- safe to apply ahead of the code.

ALTER TABLE public.eu_news_items
    ADD COLUMN IF NOT EXISTS body_txt    TEXT,
    ADD COLUMN IF NOT EXISTS body_html   TEXT,
    ADD COLUMN IF NOT EXISTS body_source TEXT;

COMMENT ON COLUMN public.eu_news_items.body_txt IS
    'Composed plain-text body (title + summary + provenance). NOT the scraped article: this table never held one. See body_source.';
COMMENT ON COLUMN public.eu_news_items.body_html IS
    'Composed HTML body, same content as body_txt. NOT the scraped article. See body_source.';
COMMENT ON COLUMN public.eu_news_items.body_source IS
    'How the body was produced: composed:title+summary | composed:title. NULL = not yet composed.';

-- Partial index on the uncomposed set, so the backfill and any freshness check can
-- find "rows still needing a body" without scanning 10k rows.
CREATE INDEX IF NOT EXISTS idx_eu_news_items_body_pending
    ON public.eu_news_items (created_at DESC)
    WHERE body_source IS NULL;
