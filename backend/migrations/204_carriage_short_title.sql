-- 204_carriage_short_title.sql
--
-- Cache a human-readable short name per legislative file.
--
-- WHY: legislative_carriages.title holds the official EU legal title, which
-- runs 150-400 characters and puts the subject at the very end:
--
--   "Council Decision (EU) 2026/1544 of 17 November 2025 on the conclusion,
--    on behalf of the Union, of the Protocol on the implementation of the
--    Sustainable Fisheries Partnership Agreement between the European Union
--    and the Government of the Cook Islands (2025-2032)"
--
-- Surfaces that list files (the My EU Bubble briefing cards, the Overview
-- cockpit, the file modal) cannot show that. Truncating from the front yields
-- a code rather than a name: "Council Decision (EU) 2026/1544".
--
-- services/legislative/title_display.py resolves curated aliases first
-- (procedure_aliases.json by OEIL reference, the legislation acronym KB by
-- CELEX), but those cover the files Brussels talks about, never the long tail
-- of routine acts. For that tail
-- services/legislative/title_synthesiser.py compresses the official title with
-- the free open-model chain, and the result is cached here.
--
-- Cached, not computed per request: a dashboard load must never wait on a
-- model. scripts/backfill_carriage_short_titles.py fills the column; NULL is
-- a valid state and means "fall back to the instrument designation".
--
-- Data-API grants are mandatory on public.* changes (see
-- memory/feedback_supabase_data_api_grants.md). This migration adds a column
-- to an existing table, so the table's own RLS policies and grants continue
-- to apply and no new GRANT is required.

ALTER TABLE public.legislative_carriages
    ADD COLUMN IF NOT EXISTS short_title TEXT;

COMMENT ON COLUMN public.legislative_carriages.short_title IS
    'Human-readable short name for the file (max ~60 chars). Curated alias, '
    'else AI-synthesised from title and checked for faithfulness, else NULL. '
    'NULL means callers fall back to the parsed instrument designation. '
    'Written by scripts/backfill_carriage_short_titles.py.';
