-- 200_catalan_law_eurovoc.sql
-- Marries the Catalan EU acquis (catalan_translations) to the Catalan EuroVoc taxonomy
-- (eurovoc_concepts). Each translated act links to its EuroVoc descriptor concepts, so
-- users can (a) see what a law is about in Catalan and (b) find laws by topic.
-- Source: gold_labels.jsonl (official Cellar EuroVoc). Annexes inherit their parent's labels.

CREATE TABLE IF NOT EXISTS catalan_law_eurovoc (
    celex        TEXT NOT NULL,
    concept_uri  TEXT NOT NULL,
    notation     TEXT NOT NULL,           -- denormalised descriptor notation for fast joins
    relation     TEXT NOT NULL DEFAULT 'gold',  -- 'gold' (own labels) | 'inherited' (from parent act)
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (celex, concept_uri)
);

CREATE INDEX IF NOT EXISTS idx_cle_celex     ON catalan_law_eurovoc (celex);
CREATE INDEX IF NOT EXISTS idx_cle_uri       ON catalan_law_eurovoc (concept_uri);
CREATE INDEX IF NOT EXISTS idx_cle_notation  ON catalan_law_eurovoc (notation);

-- Supabase Data API: RLS + public-read policy + explicit grants (mandatory on new public.* tables)
ALTER TABLE catalan_law_eurovoc ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS catalan_law_eurovoc_public_read ON catalan_law_eurovoc;
CREATE POLICY catalan_law_eurovoc_public_read ON catalan_law_eurovoc FOR SELECT USING (true);
GRANT SELECT ON catalan_law_eurovoc TO anon, authenticated;
GRANT ALL    ON catalan_law_eurovoc TO service_role;
