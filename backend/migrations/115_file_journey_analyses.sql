-- Migration 115 — Legislative-journey comparative analysis (Position Analysis)
--
-- AI-driven comparison of the text journey of a dossier: the Commission
-- proposal -> the rapporteur's draft report -> other MEPs' amendments -> the
-- rapporteur/shadows' compromise amendments -> the final committee voting list.
-- Resolution files skip the proposal layer. Non-Anthropic engine
-- (Mistral->GPT-4->Gemini), full-text long-context, precomputed for tracked
-- files and cached. Shared, read-only, derived public data.
--
-- Two tables:
--   file_journey_analyses  — one row per procedure (the analysis itself)
--   emeeting_doc_text_cache — extracted PDF text, one row per immutable PDF URL
BEGIN;

-- Extracted text cache: each meetdocs PDF is immutable once published, so we
-- fetch + pdf-extract it once and reuse. Keyed by URL.
CREATE TABLE IF NOT EXISTS emeeting_doc_text_cache (
    pdf_url       TEXT PRIMARY KEY,
    text          TEXT,
    char_count    INTEGER NOT NULL DEFAULT 0,
    page_count    INTEGER,
    truncated     BOOLEAN NOT NULL DEFAULT FALSE,
    extracted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- The comparative analysis, one row per dossier (procedure).
CREATE TABLE IF NOT EXISTS file_journey_analyses (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    procedure_ref    TEXT NOT NULL UNIQUE,
    carriage_id      UUID,
    is_legislative   BOOLEAN NOT NULL DEFAULT TRUE,
    -- Hash of the contributing document set; lets precompute skip unchanged
    -- dossiers and recompute when a new draft report / amendment / compromise /
    -- voting list lands.
    doc_set_hash     TEXT NOT NULL,
    proposal_celex   TEXT,
    -- Per-layer payload: [{kind, label, doc_ref, source_url, pdf_url,
    --                      char_count, truncated, summary}]
    layers           JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- Cross-layer comparison: {overview, by_layer:{...}, contested_points:[...],
    --                          where_the_fight_is, caveats}
    comparison       JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Short version for the file-detail modal.
    summary          TEXT,
    engine           TEXT,
    model            TEXT,
    source_doc_count INTEGER NOT NULL DEFAULT 0,
    status           TEXT NOT NULL DEFAULT 'ready',  -- ready | generating | error
    generated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_journey_carriage ON file_journey_analyses (carriage_id);
CREATE INDEX IF NOT EXISTS ix_journey_generated ON file_journey_analyses (generated_at DESC NULLS LAST);

-- Supabase Data API grants (mandatory). Derived public data: anyone may read;
-- only the backend service writes.
ALTER TABLE emeeting_doc_text_cache ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS emeeting_doc_text_cache_public_read ON emeeting_doc_text_cache;
CREATE POLICY emeeting_doc_text_cache_public_read ON emeeting_doc_text_cache
    FOR SELECT TO anon, authenticated USING (true);
GRANT SELECT ON emeeting_doc_text_cache TO anon, authenticated;
GRANT ALL ON emeeting_doc_text_cache TO service_role;

ALTER TABLE file_journey_analyses ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS file_journey_analyses_public_read ON file_journey_analyses;
CREATE POLICY file_journey_analyses_public_read ON file_journey_analyses
    FOR SELECT TO anon, authenticated USING (true);
GRANT SELECT ON file_journey_analyses TO anon, authenticated;
GRANT ALL ON file_journey_analyses TO service_role;

COMMIT;
