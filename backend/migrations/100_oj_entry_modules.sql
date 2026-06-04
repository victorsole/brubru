-- Migration 100 — My OJ "cool modules": plain-language explanation + tags.
--
-- Adds, to oj_entries:
--   plain_explanation  one-sentence jargon-free gloss (AI, generated once at
--                      sync time via the cost-capped provider — Mistral only,
--                      NO Anthropic — and cached here; see services/scrapers/
--                      oj_explainer.py). Helps users understand what they read.
--   change_kind        new | amends | renews | repeals | extends | suspends |
--                      corrects  (parsed from the title; the "what it changes" tag)
--   theme              plain-language topic cluster (Fisheries, Feed additives,
--                      Sanctions (CFSP), ...) for the day's theme grouping.
--
-- Safe to re-run.

BEGIN;

ALTER TABLE oj_entries
    ADD COLUMN IF NOT EXISTS plain_explanation TEXT,
    ADD COLUMN IF NOT EXISTS change_kind       TEXT,
    ADD COLUMN IF NOT EXISTS theme             TEXT;

CREATE INDEX IF NOT EXISTS ix_oj_entries_theme ON oj_entries (theme);

COMMIT;
