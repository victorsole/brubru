-- 229: give eu_news_items a real last-fetch anchor.
--
-- WHY
-- ---
-- /api/v2/news/latest classifies every body three ways: `not_fetched` (the cron is
-- not reaching it, ours to fix), `undated_items` (ours to fix) and
-- `publisher_quiet` (not a defect). Computing that needs to know when we last
-- FETCHED the body, separately from when its newest item was published.
--
-- economy_items has `fetched_at` and gets a real verdict. eu_news_items has only
-- `scraped_at`, which is `default=datetime.now` on the model -- set on INSERT and
-- never again -- so it is a FIRST-SEEN timestamp, not a fetch anchor. Reading it as
-- one is the exact mistake that invented 17 dead fetchers on 8 September 2026
-- (feedback_two_date_anchors_diagnose_scrapers), so the endpoint deliberately
-- passed NULL::timestamptz for the whole institutional half and reported
-- `fetch_time_unknown` instead of guessing.
--
-- The cost of that honesty was real: Council news went 70 days without a row and
-- the endpoint could not say whether that was our cron or the Council's silence.
-- It was our cron. `fetch_time_unknown` was the correct verdict and a useless one.
--
-- WHAT
-- ----
-- A nullable `fetched_at`. Nullable on purpose and NOT backfilled: we do not know
-- when any existing row was last fetched, and inventing a value would fabricate the
-- very reading this column exists to make trustworthy. Every body reads
-- `fetch_time_unknown` until its next sync stamps it, which is honest and
-- self-healing.
--
-- The writers stamp it for every row they SEE, including rows they leave otherwise
-- unchanged -- a sighting is a fetch even when nothing changed. That is the whole
-- point: the previous upsert returned "skipped" and touched nothing, so a body
-- being fetched successfully every hour looked identical to one nobody was reading.

ALTER TABLE public.eu_news_items
    ADD COLUMN IF NOT EXISTS fetched_at TIMESTAMPTZ;

COMMENT ON COLUMN public.eu_news_items.fetched_at IS
    'When a sync last SAW this row on its source listing, stamped on every sighting '
    'including unchanged ones. The ingestion anchor. NOT scraped_at, which is '
    'first-seen only. NULL means never stamped since migration 229 -- read as '
    'unknown, never as not-fetched.';

-- max(fetched_at) per institution is the only access pattern (/api/v2/news/latest
-- groups by body), so index the pair rather than the timestamp alone.
CREATE INDEX IF NOT EXISTS idx_eu_news_items_institution_fetched_at
    ON public.eu_news_items (institution, fetched_at DESC NULLS LAST);

-- Supabase Data API grants are mandatory on public.* tables (the default grant was
-- removed 30 Oct 2026, so a replay breaks without these). Adding a column does not
-- change table-level grants, and RLS/policies are unchanged here, so nothing further
-- is required for this migration -- recorded explicitly so the omission reads as
-- deliberate rather than forgotten.
