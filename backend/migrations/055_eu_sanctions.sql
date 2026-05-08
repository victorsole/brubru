-- 055_eu_sanctions.sql
-- EU Financial Sanctions Database (CFSP / Restrictive Measures)
-- Source: https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList/content?token=dG9rZW4tMjAxNw
--
-- The upstream CSV is wide (59 cols) and "long" — multiple rows per
-- sanctioned entity for each name variant, address, birth detail, ID,
-- citizenship. Backfill aggregates these into one row per (entity, programme).

CREATE TABLE IF NOT EXISTS eu_sanctions (
    id                            BIGSERIAL PRIMARY KEY,
    entity_logical_id             INTEGER NOT NULL,
    subject_type                  CHAR(1) NOT NULL CHECK (subject_type IN ('P', 'E')),
    programme                     VARCHAR(20) NOT NULL,

    -- Legal basis
    legal_basis_title             TEXT,
    legal_basis_publication_date  DATE,
    legal_basis_url               TEXT,

    -- Primary identity (canonical name, taken from the first non-empty Naal_*)
    full_name                     TEXT,
    first_name                    TEXT,
    middle_name                   TEXT,
    last_name                     TEXT,
    gender                        CHAR(1),
    title                         TEXT,
    function                      TEXT,

    -- Aggregated multi-row records
    aliases                       JSONB DEFAULT '[]'::jsonb,
    addresses                     JSONB DEFAULT '[]'::jsonb,
    birth_details                 JSONB DEFAULT '[]'::jsonb,
    identification_documents      JSONB DEFAULT '[]'::jsonb,
    citizenships                  TEXT[] DEFAULT ARRAY[]::TEXT[],

    remark                        TEXT,
    date_file                     DATE,
    eu_ref_num                    VARCHAR(50),

    created_at                    TIMESTAMPTZ DEFAULT NOW(),
    updated_at                    TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT eu_sanctions_unique_entity_programme
        UNIQUE (entity_logical_id, programme)
);

CREATE INDEX IF NOT EXISTS idx_eu_sanctions_programme
    ON eu_sanctions (programme);
CREATE INDEX IF NOT EXISTS idx_eu_sanctions_subject_type
    ON eu_sanctions (subject_type);
CREATE INDEX IF NOT EXISTS idx_eu_sanctions_entity_id
    ON eu_sanctions (entity_logical_id);
CREATE INDEX IF NOT EXISTS idx_eu_sanctions_full_name_search
    ON eu_sanctions USING gin (to_tsvector('simple', COALESCE(full_name, '')));
CREATE INDEX IF NOT EXISTS idx_eu_sanctions_eu_ref_num
    ON eu_sanctions (eu_ref_num);
CREATE INDEX IF NOT EXISTS idx_eu_sanctions_date_file
    ON eu_sanctions (date_file DESC NULLS LAST);

-- RLS — public read; writes only via backfill script using service role.
ALTER TABLE eu_sanctions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "eu_sanctions_public_read" ON eu_sanctions;
CREATE POLICY "eu_sanctions_public_read"
    ON eu_sanctions FOR SELECT
    USING (true);

COMMENT ON TABLE eu_sanctions IS
    'EU Restrictive Measures (CFSP financial sanctions) consolidated list. '
    'Aggregated from the public CSV at webgate.ec.europa.eu/fsd/fsf. '
    'One row per (entity_logical_id, programme).';
