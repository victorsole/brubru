-- 040 — add raw pdf_url to commission_documents so /api/v1/commission-register-documents
-- can serve the actual PDF asset, not just the portal landing page.
-- Created: 26 April 2026.

ALTER TABLE commission_documents
    ADD COLUMN IF NOT EXISTS pdf_url TEXT,
    ADD COLUMN IF NOT EXISTS document_register_category VARCHAR(50),
    ADD COLUMN IF NOT EXISTS source_url TEXT;

-- Backfill: when portal_url ends in .pdf, copy it into pdf_url.
UPDATE commission_documents
SET pdf_url = portal_url
WHERE pdf_url IS NULL
  AND portal_url ILIKE '%.pdf';

CREATE INDEX IF NOT EXISTS ix_commission_documents_register_category
    ON commission_documents(document_register_category);
CREATE INDEX IF NOT EXISTS ix_commission_documents_publication_date
    ON commission_documents(publication_date DESC);
