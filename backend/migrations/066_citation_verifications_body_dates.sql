-- 066_citation_verifications_body_dates.sql
-- Adds the 5 mandatory v1 datapoints to the citation-verifier cache:
--   public_url       — citizen-facing EUR-Lex URL (derived from CELEX)
--   body_text        — plain-text body of the document
--   body_html        — HTML body (Cellar XHTML manifestation)
--   body_fetched_at  — when WE fetched the body (separate from verified_at)
--   creation_date    — when this CELEX first entered our eu_laws corpus (scrape date)
--   document_date    — the document's adoption / publication date
--
-- Body content is fetched from Cellar XHTML on first verify and cached alongside
-- the existing TTL pattern (30d ok / 24h broken / 1h unknown).

ALTER TABLE citation_verifications
    ADD COLUMN IF NOT EXISTS public_url       TEXT,
    ADD COLUMN IF NOT EXISTS body_text        TEXT,
    ADD COLUMN IF NOT EXISTS body_html        TEXT,
    ADD COLUMN IF NOT EXISTS body_fetched_at  TIMESTAMP,
    ADD COLUMN IF NOT EXISTS creation_date    TIMESTAMP,
    ADD COLUMN IF NOT EXISTS document_date    DATE;

CREATE INDEX IF NOT EXISTS idx_citation_verifications_doc_date
    ON citation_verifications (document_date DESC NULLS LAST);

COMMENT ON COLUMN citation_verifications.public_url IS
    'Citizen-facing EUR-Lex URL (https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:...). '
    'Distinct from resolved_url which is the Cellar manifestation (cellar/<UUID>/DOC_1).';
COMMENT ON COLUMN citation_verifications.body_text IS
    'Plain-text body of the verified document (Cellar XHTML stripped to text).';
COMMENT ON COLUMN citation_verifications.body_html IS
    'HTML body of the verified document (Cellar XHTML manifestation, EN).';
COMMENT ON COLUMN citation_verifications.creation_date IS
    'When the CELEX first entered Brubru''s eu_laws corpus (our scrape date).';
COMMENT ON COLUMN citation_verifications.document_date IS
    'The document''s adoption or publication date (eu_laws.date).';
