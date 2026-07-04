-- 199_eurovoc_taxonomy.sql
-- The full EuroVoc thesaurus as a walkable tree: 21 domains -> ~128 microthesauri
-- -> ~7,029 descriptors, with the skos:broader hierarchy and multilingual labels.
-- Source: Cellar SPARQL (publications.europa.eu/webapi/rdf/sparql). One row per
-- concept, keyed by its stable EuroVoc URI so every concept stays linkable to
-- EUR-Lex and to the Catalan legislation pages.
--
-- Labels are stored as JSONB {lang: label}. Loaded now with en/es/fr/it/nl (the
-- languages EuroVoc publishes). Catalan is NOT an official EuroVoc language, so
-- the "ca" key is intentionally left absent: the dedicated Catalan-translation
-- session fills labels->>'ca' (and alt_labels->'ca') per concept, keyed by
-- concept_uri, to produce the first Catalan EuroVoc and use it as the official
-- taxonomy of /legislacio-ue-catala/.

CREATE TABLE IF NOT EXISTS eurovoc_concepts (
    id                  BIGSERIAL PRIMARY KEY,
    concept_uri         TEXT NOT NULL UNIQUE,          -- http://eurovoc.europa.eu/1764
    notation            VARCHAR(24),                   -- 1764 (descriptor) / 2826 (microthesaurus) / 04 (domain)
    concept_type        VARCHAR(16) NOT NULL,          -- domain | microthesaurus | descriptor
    labels              JSONB NOT NULL DEFAULT '{}'::jsonb,   -- {"en":..,"es":..,"fr":..,"it":..,"nl":..}  ("ca" added later)
    alt_labels          JSONB,                          -- {"en":[...], ...} non-preferred terms
    domain_uri          TEXT,                           -- descriptor/microthesaurus -> its domain
    microthesaurus_uri  TEXT,                           -- descriptor -> its microthesaurus
    broader_uri         TEXT,                           -- descriptor -> parent descriptor (skos:broader)
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eurovoc_type      ON eurovoc_concepts (concept_type);
CREATE INDEX IF NOT EXISTS idx_eurovoc_notation  ON eurovoc_concepts (notation);
CREATE INDEX IF NOT EXISTS idx_eurovoc_domain    ON eurovoc_concepts (domain_uri);
CREATE INDEX IF NOT EXISTS idx_eurovoc_mt        ON eurovoc_concepts (microthesaurus_uri);
CREATE INDEX IF NOT EXISTS idx_eurovoc_broader   ON eurovoc_concepts (broader_uri);
CREATE INDEX IF NOT EXISTS idx_eurovoc_labels    ON eurovoc_concepts USING gin (labels);

-- Supabase Data API: RLS + public-read policy + explicit grants (mandatory on new public.* tables)
ALTER TABLE eurovoc_concepts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS eurovoc_concepts_public_read ON eurovoc_concepts;
CREATE POLICY eurovoc_concepts_public_read ON eurovoc_concepts FOR SELECT USING (true);

GRANT SELECT ON eurovoc_concepts TO anon, authenticated;
GRANT ALL    ON eurovoc_concepts TO service_role;
GRANT USAGE, SELECT ON SEQUENCE eurovoc_concepts_id_seq TO service_role;
