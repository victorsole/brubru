-- 048_eu_vocabularies.sql
--
-- Phase 0 of the EU Vocabularies plan (docs/applications/euvoc.md).
-- Two new tables:
--   1. eu_authority_labels — local cache of skos:prefLabel rows pulled from
--      the Cellar SPARQL endpoint for every NAL we care about. Phase 1 fills
--      it via scripts/sync_eu_authority_labels.py.
--   2. brubru_dataset_catalog — Brubru's own DCAT-AP self-catalogue rows.
--      Phase 2 seeds it and serves /api/datasets.{ttl,rdf,json}.
--
-- Both tables have RLS enabled per Brubru security rule
-- (memory/feedback_supabase_rls.md, 15 Apr 2026).

-- ============================================================================
-- 1. eu_authority_labels — SPARQL-backed label cache
-- ============================================================================
CREATE TABLE IF NOT EXISTS eu_authority_labels (
    -- Concept URI from the Publications Office authority-tables namespace,
    -- e.g. http://publications.europa.eu/resource/authority/corporate-body/EP.
    uri                 TEXT NOT NULL,
    -- ISO-639 lowercase 2-letter language tag (en, fr, es, ca, it, nl).
    lang                VARCHAR(8) NOT NULL,
    -- skos:prefLabel
    pref_label          TEXT NOT NULL,
    -- skos:altLabel and acronyms in the same language (empty array if none).
    alt_labels          TEXT[] NOT NULL DEFAULT '{}'::TEXT[],
    -- The dataset URI the concept belongs to,
    -- e.g. http://publications.europa.eu/resource/dataset/corporate-body.
    source_dataset_uri  TEXT NOT NULL,
    -- When this row was last refreshed from SPARQL.
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (uri, lang)
);

-- Lookup paths — chat resolves URI -> label, alt-label search needs
-- accent-tolerant trigram-style matching, dataset filter for batch refresh.
CREATE INDEX IF NOT EXISTS ix_eal_dataset       ON eu_authority_labels (source_dataset_uri);
CREATE INDEX IF NOT EXISTS ix_eal_pref_label    ON eu_authority_labels (LOWER(pref_label));
CREATE INDEX IF NOT EXISTS ix_eal_alt_gin       ON eu_authority_labels USING GIN (alt_labels);
CREATE INDEX IF NOT EXISTS ix_eal_lang          ON eu_authority_labels (lang);

ALTER TABLE eu_authority_labels ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_eu_authority_labels" ON eu_authority_labels
    FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "authenticated_read_eu_authority_labels" ON eu_authority_labels
    FOR SELECT TO authenticated USING (TRUE);

COMMENT ON TABLE eu_authority_labels IS
    'Local cache of skos:prefLabel + skos:altLabel rows from the EU Publications '
    'Office authority tables. Filled nightly by Phase 1 sync. PK (uri, lang). '
    'See docs/applications/euvoc.md and memory/reference_eu_vocabularies.md.';

COMMENT ON COLUMN eu_authority_labels.uri IS 'Concept URI (publications.europa.eu/resource/authority/...).';
COMMENT ON COLUMN eu_authority_labels.lang IS 'ISO-639 lowercase 2-letter tag.';
COMMENT ON COLUMN eu_authority_labels.alt_labels IS 'skos:altLabel + acronyms in the same language.';
COMMENT ON COLUMN eu_authority_labels.source_dataset_uri IS 'publications.europa.eu/resource/dataset/{name}.';

-- ============================================================================
-- 2. brubru_dataset_catalog — Brubru's own DCAT-AP self-catalogue
-- ============================================================================
CREATE TABLE IF NOT EXISTS brubru_dataset_catalog (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- The IRI we publish for this dataset (Brubru-owned URI in the
    -- brubru.beresol.eu namespace).
    dcat_uri            TEXT NOT NULL UNIQUE,
    title               TEXT NOT NULL,
    -- Multi-language description object: { "en": "...", "ca": "...", ... }.
    description         JSONB NOT NULL DEFAULT '{}'::JSONB,
    -- EuroVoc concept URIs that classify this dataset for dcat:theme.
    dcat_theme          TEXT[] NOT NULL DEFAULT '{}'::TEXT[],
    -- List of dcat:Distribution objects:
    --   [{ "access_url": "...", "media_type": "text/turtle", "format": "TTL" }]
    distribution        JSONB NOT NULL DEFAULT '[]'::JSONB,
    -- SPDX license identifier or human-readable license string.
    license             TEXT,
    -- dct:accrualPeriodicity (e.g. "P1D" daily, "P1W" weekly, "irregular").
    accrual_periodicity TEXT,
    -- Last time this catalogue entry was validated against DCAT-AP shapes.
    last_validated_at   TIMESTAMPTZ,
    -- When this row was created / last updated.
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_bdc_theme_gin     ON brubru_dataset_catalog USING GIN (dcat_theme);
CREATE INDEX IF NOT EXISTS ix_bdc_updated_at    ON brubru_dataset_catalog (updated_at);

ALTER TABLE brubru_dataset_catalog ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_brubru_dataset_catalog" ON brubru_dataset_catalog
    FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
-- Public read is intentional — the DCAT-AP feed is meant to be harvested.
CREATE POLICY "anon_read_brubru_dataset_catalog" ON brubru_dataset_catalog
    FOR SELECT TO anon USING (TRUE);
CREATE POLICY "authenticated_read_brubru_dataset_catalog" ON brubru_dataset_catalog
    FOR SELECT TO authenticated USING (TRUE);

COMMENT ON TABLE brubru_dataset_catalog IS
    'Brubru self-catalogue rows that feed /api/datasets.{ttl,rdf,json} as a '
    'DCAT-AP-compliant data publisher description. Phase 2 of '
    'docs/applications/euvoc.md.';

COMMENT ON COLUMN brubru_dataset_catalog.dcat_uri IS 'The IRI Brubru publishes for this dataset.';
COMMENT ON COLUMN brubru_dataset_catalog.description IS 'Multi-language JSONB { "en": ..., "ca": ..., ... }.';
COMMENT ON COLUMN brubru_dataset_catalog.dcat_theme IS 'EuroVoc concept URIs (http://eurovoc.europa.eu/...).';
COMMENT ON COLUMN brubru_dataset_catalog.distribution IS 'JSONB array of dcat:Distribution objects.';
COMMENT ON COLUMN brubru_dataset_catalog.accrual_periodicity IS 'dct:accrualPeriodicity ISO-8601 duration or text.';

-- ============================================================================
-- 3. updated_at trigger for brubru_dataset_catalog
-- ============================================================================
CREATE OR REPLACE FUNCTION trg_brubru_dataset_catalog_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS brubru_dataset_catalog_updated_at_trigger ON brubru_dataset_catalog;
CREATE TRIGGER brubru_dataset_catalog_updated_at_trigger
BEFORE UPDATE ON brubru_dataset_catalog
FOR EACH ROW EXECUTE FUNCTION trg_brubru_dataset_catalog_updated_at();
