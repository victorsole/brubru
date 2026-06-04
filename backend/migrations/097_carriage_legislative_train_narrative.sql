-- 097: Store the EP Legislative Train editorial narrative on the carriage.
--
-- OEIL gives structured procedure metadata (refs, dates, committee, event log)
-- but no explanation. The EP Legislative Train file page carries a human-written
-- "state of play" narrative (purpose, political background, funding mechanics,
-- EP/Council process, latest developments) that is high-value for MEUB analysis
-- and Chat grounding. We join it to the carriage by OEIL procedure ref and store
-- the narrative text, the source URL, and when we last fetched it.

ALTER TABLE legislative_carriages
    ADD COLUMN IF NOT EXISTS legislative_train_summary    TEXT,
    ADD COLUMN IF NOT EXISTS legislative_train_url         TEXT,
    ADD COLUMN IF NOT EXISTS legislative_train_updated_at  TIMESTAMPTZ;
