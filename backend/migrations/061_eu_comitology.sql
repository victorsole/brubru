-- 061_eu_comitology.sql
-- EU Comitology Register: documents from committee meetings overseeing
-- the Commission's implementing acts. Source: REST API at
-- ec.europa.eu/transparency/comitology-register/core/api/front
-- (cracked via Playwright network capture — the SPA was masking the real
-- backend path). ~112,832 documents and ~300 committees as of 2026-05.

CREATE TABLE IF NOT EXISTS eu_comitology_documents (
    id                  BIGSERIAL PRIMARY KEY,
    document_reference  VARCHAR(40) NOT NULL UNIQUE,
    title               TEXT,
    meeting_code        VARCHAR(40),
    committee_code      VARCHAR(40),
    committee_title     TEXT,
    document_type       JSONB,
    document_type_label VARCHAR(60),
    document_type_letter CHAR(1),

    creation_date       TIMESTAMPTZ,
    update_date         TIMESTAMPTZ,
    meeting_start_date  TIMESTAMPTZ,
    meeting_end_date    TIMESTAMPTZ,

    version             INTEGER,
    public_url          TEXT,

    has_body            BOOLEAN  NOT NULL DEFAULT false,
    body_html           TEXT,
    body_text           TEXT,
    body_source         VARCHAR(24),

    fetched_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ecmd_committee   ON eu_comitology_documents (committee_code);
CREATE INDEX IF NOT EXISTS idx_ecmd_meeting     ON eu_comitology_documents (meeting_code);
CREATE INDEX IF NOT EXISTS idx_ecmd_type        ON eu_comitology_documents (document_type_letter);
CREATE INDEX IF NOT EXISTS idx_ecmd_creation    ON eu_comitology_documents (creation_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_ecmd_meeting_date ON eu_comitology_documents (meeting_start_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_ecmd_title       ON eu_comitology_documents USING gin (to_tsvector('english', COALESCE(title,'')));

ALTER TABLE eu_comitology_documents ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "ecmd_public_read" ON eu_comitology_documents;
CREATE POLICY "ecmd_public_read" ON eu_comitology_documents FOR SELECT USING (true);

CREATE TABLE IF NOT EXISTS eu_comitology_committees (
    id                  BIGSERIAL PRIMARY KEY,
    code                VARCHAR(40) NOT NULL UNIQUE,
    title               TEXT,
    dg_code             VARCHAR(20),
    dg_title            TEXT,
    parent_code         VARCHAR(40),
    abolished_since     TIMESTAMPTZ,
    rules_procedure_filename TEXT,
    public_url          TEXT,
    raw_json            JSONB,

    fetched_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ecmc_dg     ON eu_comitology_committees (dg_code);
CREATE INDEX IF NOT EXISTS idx_ecmc_parent ON eu_comitology_committees (parent_code);

ALTER TABLE eu_comitology_committees ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "ecmc_public_read" ON eu_comitology_committees;
CREATE POLICY "ecmc_public_read" ON eu_comitology_committees FOR SELECT USING (true);

COMMENT ON TABLE eu_comitology_documents IS
    'Comitology Register documents. Source: REST API at '
    'ec.europa.eu/transparency/comitology-register/core/api/front/. '
    'Backing table for /api/v1/specialised/comitology-documents.';
COMMENT ON TABLE eu_comitology_committees IS
    'Comitology Register committees overseeing Commission implementing acts. '
    'Backing table for /api/v1/specialised/comitology-committees.';
