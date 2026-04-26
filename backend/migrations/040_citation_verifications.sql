-- 040 — citation_verifications cache table.
-- Backs services/citation_verifier.py and /api/v1/verify-citation/{ref}.
-- Sprint 1a of the Industry Benchmarks integration (CoCounsel-style citation
-- verification, log-only first to measure latency before any UX changes).
-- Created: 26 April 2026.

CREATE TABLE IF NOT EXISTS citation_verifications (
    -- Canonical reference string. CELEX numbers stored verbatim
    -- (e.g. 32016R0679, 52021PC0206). COM refs are first converted to CELEX
    -- and stored under the converted form. OEIL refs stored verbatim
    -- (e.g. 2021/0106(COD)).
    ref VARCHAR(64) PRIMARY KEY,

    -- celex | com_as_celex | oeil
    kind VARCHAR(16) NOT NULL,

    -- ok | broken | unknown (network error / timeout)
    status VARCHAR(16) NOT NULL,

    -- Resolved canonical URL when status=ok. Null for broken/unknown.
    resolved_url TEXT,

    -- Last HTTP status returned by the upstream HEAD request.
    -- Null for cache rows written without a network call (none yet).
    http_status INTEGER,

    -- Latency of the actual HTTP HEAD that produced this row, in milliseconds.
    -- Used by measure_citation_latency.py to compute cold p50/p95.
    latency_ms INTEGER,

    -- The original form the AI wrote (e.g. "COM(2021) 206") if different from
    -- ref after normalisation. Helps debug normalisation issues.
    original_form VARCHAR(128),

    verified_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- TTL governance:
    --   ok rows  -> 30 days (CELEX entries are immutable once published)
    --   broken   -> 24 hours (might be transient)
    --   unknown  -> 1 hour
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_citation_verifications_kind ON citation_verifications(kind);
CREATE INDEX IF NOT EXISTS ix_citation_verifications_status ON citation_verifications(status);
CREATE INDEX IF NOT EXISTS ix_citation_verifications_expires_at ON citation_verifications(expires_at);

-- RLS per learned rule (15 Apr 2026 PostgREST vulnerability fix).
-- The cache is non-sensitive (it only confirms existence of public EU
-- documents) but consistency demands every public.* table has RLS.
ALTER TABLE citation_verifications ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
    EXECUTE 'CREATE POLICY allow_read_citation_verifications ON citation_verifications FOR SELECT USING (true)';
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    EXECUTE 'CREATE POLICY allow_write_citation_verifications ON citation_verifications FOR INSERT WITH CHECK (true)';
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    EXECUTE 'CREATE POLICY allow_update_citation_verifications ON citation_verifications FOR UPDATE USING (true) WITH CHECK (true)';
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
