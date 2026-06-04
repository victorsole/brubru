-- Migration 099 — Official Journal daily entries (MEUB "My OJ")
--
-- WHY
-- ---
-- The EUR-Lex OJ daily views (L = legislation, C = information & notices) list
-- every act published on a given day, but the page is WAF-walled and ungainly.
-- We parse it (Playwright + services/scrapers/oj_scraper.py) into one row per
-- act, derive the CELEX for L-series legislation, and match it back to a tracked
-- legislative carriage / adopted text so the OJ links to the rest of MEUB —
-- especially My Tracked Files. The "My OJ" tab then shows the day's acts,
-- filterable by the user's Policy Interests.
--
-- Permission policy: OJ acts are PUBLIC reference data (like eu_laws).
--   anon + authenticated: SELECT; service_role: ALL (the sync writes).
--
-- Safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS oj_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Stable dedup key: the OJ id (e.g. 'L_202601144') or '<series>|<number>'.
    entry_key       TEXT NOT NULL UNIQUE,

    oj_date         DATE NOT NULL,              -- OJ publication date
    series          TEXT NOT NULL CHECK (series IN ('L', 'C')),
    oj_number       TEXT NOT NULL,              -- '2026/1144' (L) or 'C/2026/2942' (C)
    oj_id           TEXT,                        -- EUR-Lex OJ uri id, 'L_202601144'
    celex           TEXT,                        -- derived for L-series, '32026R1144'

    title           TEXT NOT NULL,
    act_type        TEXT,                        -- 'Implementing Regulation', 'Decision', ...
    category        TEXT,                        -- 'Regulations', 'Decisions', 'Information and notices'
    institution     TEXT,                        -- 'Commission', 'Council', 'European Parliament and Council', ...
    eurlex_url      TEXT,

    -- MEUB bridge: when this act maps (by CELEX) to a known dossier.
    carriage_id     UUID REFERENCES legislative_carriages(id) ON DELETE SET NULL,
    matched_procedure_ref TEXT,                  -- OEIL ref of the matched carriage
    matched_ta_reference  TEXT,                  -- adopted-text ref if matched

    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_oj_entries_date ON oj_entries (oj_date DESC);
CREATE INDEX IF NOT EXISTS ix_oj_entries_series ON oj_entries (series);
CREATE INDEX IF NOT EXISTS ix_oj_entries_celex ON oj_entries (celex);
CREATE INDEX IF NOT EXISTS ix_oj_entries_carriage ON oj_entries (carriage_id);
CREATE INDEX IF NOT EXISTS ix_oj_entries_act_type ON oj_entries (act_type);
CREATE INDEX IF NOT EXISTS ix_oj_entries_institution ON oj_entries (institution);

ALTER TABLE oj_entries ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS oj_entries_public_read ON oj_entries;
CREATE POLICY oj_entries_public_read ON oj_entries
    FOR SELECT TO anon, authenticated USING (true);

-- Data API grants (hard rule, set 15 May 2026): public-read -> anon+authenticated
-- SELECT, service_role ALL.
GRANT SELECT ON oj_entries TO anon, authenticated;
GRANT ALL ON oj_entries TO service_role;

COMMIT;
