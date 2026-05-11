-- 067_commission_documents_body_html.sql
-- Adds body_html column to commission_documents so we can store the Cellar
-- XHTML manifestation for CELEX-bearing rows (COM/SWD/JOIN/OJ acts).
-- text_body already exists; this is the HTML twin for /api/v1/commission-
-- register-documents to expose body_text + body_html uniformly.

ALTER TABLE commission_documents
    ADD COLUMN IF NOT EXISTS body_html TEXT;

CREATE INDEX IF NOT EXISTS idx_commission_documents_publication_date
    ON commission_documents (publication_date DESC NULLS LAST);

COMMENT ON COLUMN commission_documents.body_html IS
    'HTML body of the document (Cellar XHTML manifestation, EN). Populated by '
    'backfill_commission_documents_body.py for CELEX-bearing rows; null for '
    'rows where Cellar has no XHTML manifestation (legacy COM/SWD scrapes '
    'or PDF-only acts).';
