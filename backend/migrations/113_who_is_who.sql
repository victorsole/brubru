-- Migration 113 — Who is Who (API v2 "Who is Who" folder)
--
-- The EU's official interinstitutional directory (op.europa.eu/web/who-is-who).
-- The structured source is the EU SPARQL endpoint (publications.europa.eu) — the
-- same query data.europa.eu publishes as the "EU Whoiswho" dataset CSV — which
-- returns every department (organisational unit) and every official (name +
-- position) across all EU institutions. No PDF parsing.
--
--   who_is_who_departments — one row per organisational unit (DG, directorate, unit, ...)
--   who_is_who_officials   — one row per named official (name + position + department)
--
-- Bodies composed at ingest from the real facts. Public reference data:
-- anon + authenticated SELECT, service_role ALL. Re-runnable.

BEGIN;

CREATE TABLE IF NOT EXISTS who_is_who_departments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dept_key        TEXT NOT NULL UNIQUE,        -- mnemonic or label slug
    mnemonic        TEXT,                         -- department code (e.g. AGRI)
    name            TEXT NOT NULL,                -- 'Directorate-General for Agriculture...'
    institution_uri TEXT,                         -- WHOISWHO institution URI (when present)
    official_count  INTEGER DEFAULT 0,
    public_url      TEXT,
    body_txt        TEXT,
    body_html       TEXT,
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_wiw_dept_mnemonic ON who_is_who_departments (mnemonic);

CREATE TABLE IF NOT EXISTS who_is_who_officials (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    official_key    TEXT NOT NULL UNIQUE,         -- person uri + dept + position
    name            TEXT NOT NULL,
    honorific       TEXT,
    position        TEXT,                          -- job title / position complement
    department      TEXT,                          -- department label
    mnemonic        TEXT,                          -- department code
    institution_uri TEXT,
    person_uri      TEXT,
    public_url      TEXT,
    body_txt        TEXT,
    body_html       TEXT,
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_wiw_off_dept     ON who_is_who_officials (department);
CREATE INDEX IF NOT EXISTS ix_wiw_off_mnemonic ON who_is_who_officials (mnemonic);
CREATE INDEX IF NOT EXISTS ix_wiw_off_position ON who_is_who_officials (position);

ALTER TABLE who_is_who_departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE who_is_who_officials ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS wiw_departments_public_read ON who_is_who_departments;
CREATE POLICY wiw_departments_public_read ON who_is_who_departments
    FOR SELECT TO anon, authenticated USING (true);
DROP POLICY IF EXISTS wiw_officials_public_read ON who_is_who_officials;
CREATE POLICY wiw_officials_public_read ON who_is_who_officials
    FOR SELECT TO anon, authenticated USING (true);

GRANT SELECT ON who_is_who_departments TO anon, authenticated;
GRANT ALL ON who_is_who_departments TO service_role;
GRANT SELECT ON who_is_who_officials TO anon, authenticated;
GRANT ALL ON who_is_who_officials TO service_role;

COMMIT;
