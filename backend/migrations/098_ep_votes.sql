-- Migration 098 — EP committee + plenary roll-call results (MEUB "Votes")
--
-- WHY
-- ---
-- OEIL records that a vote happened, but not how the house split. There is a
-- dormant HowTheyVote-shaped `ep_votes` table (plenary tally only, seed rows,
-- no per-MEP roll-call, no committee votes) — we deliberately do NOT touch it.
-- Instead we store the authoritative doceo roll-call (BOTH committee and
-- plenary) in dedicated tables:
--   * Committee: the doceo committee report (A-<term>-<year>-<seq>) carries a
--     "Result of final vote" tally + "FINAL VOTE BY ROLL CALL BY THE COMMITTEE
--     RESPONSIBLE" (per-MEP, grouped by +/-/0 then political group).
--   * Plenary: the doceo roll-call minutes (PV-<term>-<date>-RCV) carries the
--     per-MEP roll-call per sub-item, same group-bucketed structure.
-- Both are WAF-walled HTML (Playwright to fetch). One ep_roll_call_votes row
-- per vote + one ep_roll_call_records row per MEP, keyed by the OEIL procedure
-- ref + carriage so a vote links to the same dossier the rest of MEUB aligns
-- on. This powers the two-tab "Votes" area (Committee | Plenary) and the
-- committee->plenary delta the EP itself does not present.
--
-- Permission policy (votes are PUBLIC EP reference data, like eu_laws):
--   - anon + authenticated: SELECT (public read)
--   - service_role: ALL (the backend sync writes under the service-role key)
--
-- Safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS ep_roll_call_votes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Stable dedup key. committee -> 'committee|<report_ref>';
    -- plenary -> 'plenary|<sitting_date>|<item_number>'.
    vote_key        TEXT NOT NULL UNIQUE,

    level           TEXT NOT NULL CHECK (level IN ('committee', 'plenary')),

    -- Cross-references (join keys to the rest of MEUB).
    procedure_ref   TEXT,                      -- OEIL ref, e.g. "2025/0413(NLE)"
    carriage_id     UUID REFERENCES legislative_carriages(id) ON DELETE SET NULL,
    report_ref      TEXT,                      -- committee report code, e.g. "A10-0144/2026"
    ta_reference    TEXT,                      -- plenary adopted-text ref, e.g. "P10_TA(2026)0188"

    -- Human labels.
    title           TEXT,                      -- procedure / dossier title
    subject         TEXT,                      -- the specific thing voted (e.g. "Draft Council decision")
    committee_code  TEXT,                      -- lead committee (committee level)

    -- When + where.
    vote_date       DATE,
    sitting_date    DATE,                      -- plenary sitting (drives the PV-...-RCV URL)
    item_number     TEXT,                      -- plenary minutes item, e.g. "8.1"

    -- Outcome.
    result          TEXT,                      -- 'adopted', 'rejected'
    votes_for       INTEGER,
    votes_against   INTEGER,
    votes_abstention INTEGER,
    vote_type       TEXT,                      -- 'rcv' (roll-call), 'final', etc.

    -- Pre-computed so list cards never touch ep_roll_call_records.
    -- group_breakdown: {"ECR": {"+": 44, "-": 1, "0": 1}, "PPE": {...}, ...}
    group_breakdown JSONB DEFAULT '{}'::jsonb,
    country_breakdown JSONB DEFAULT '{}'::jsonb,   -- v2 (RCV HTML has no nationality)
    total_records   INTEGER NOT NULL DEFAULT 0,

    source_url      TEXT,
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ep_rcv_votes_procedure_ref ON ep_roll_call_votes (procedure_ref);
CREATE INDEX IF NOT EXISTS ix_ep_rcv_votes_level ON ep_roll_call_votes (level);
CREATE INDEX IF NOT EXISTS ix_ep_rcv_votes_committee ON ep_roll_call_votes (committee_code);
CREATE INDEX IF NOT EXISTS ix_ep_rcv_votes_carriage ON ep_roll_call_votes (carriage_id);
CREATE INDEX IF NOT EXISTS ix_ep_rcv_votes_vote_date ON ep_roll_call_votes (vote_date DESC NULLS LAST);


CREATE TABLE IF NOT EXISTS ep_roll_call_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vote_id         UUID NOT NULL REFERENCES ep_roll_call_votes(id) ON DELETE CASCADE,
    mep_name        TEXT NOT NULL,
    political_group TEXT,                      -- "ECR", "S&D", "Verts/ALE", "The Left", "NI", ...
    country         TEXT,                      -- v2 (RCV HTML has no nationality)
    vote_choice     TEXT NOT NULL CHECK (vote_choice IN ('+', '-', '0')),
    -- True for declared corrections / voting intentions (do NOT change the
    -- official tally; surfaced separately).
    is_intention    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ep_rcv_records_vote ON ep_roll_call_records (vote_id);
CREATE INDEX IF NOT EXISTS ix_ep_rcv_records_group ON ep_roll_call_records (political_group);

-- RLS — public read.
ALTER TABLE ep_roll_call_votes ENABLE ROW LEVEL SECURITY;
ALTER TABLE ep_roll_call_records ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ep_rcv_votes_public_read ON ep_roll_call_votes;
CREATE POLICY ep_rcv_votes_public_read ON ep_roll_call_votes
    FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS ep_rcv_records_public_read ON ep_roll_call_records;
CREATE POLICY ep_rcv_records_public_read ON ep_roll_call_records
    FOR SELECT TO anon, authenticated USING (true);

-- Data API grants (hard rule, set 15 May 2026): public-read tables grant
-- SELECT to anon + authenticated, ALL to service_role.
GRANT SELECT ON ep_roll_call_votes TO anon, authenticated;
GRANT ALL ON ep_roll_call_votes TO service_role;
GRANT SELECT ON ep_roll_call_records TO anon, authenticated;
GRANT ALL ON ep_roll_call_records TO service_role;

-- Keep updated_at fresh.
CREATE OR REPLACE FUNCTION trg_ep_rcv_votes_touch()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ep_rcv_votes_touch ON ep_roll_call_votes;
CREATE TRIGGER ep_rcv_votes_touch
    BEFORE UPDATE ON ep_roll_call_votes
    FOR EACH ROW
    EXECUTE FUNCTION trg_ep_rcv_votes_touch();

COMMIT;
