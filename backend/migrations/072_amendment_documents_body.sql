-- 072_amendment_documents_body.sql
-- Cache extracted DOCX text for /api/v1/opinions (and the other AD/PR/AM/RD
-- document_types backed by amendment_documents). Populated by
-- backend/scripts/backfill_amendment_documents_body.py from the doceo .docx
-- manifestations stored in doceo_url.

ALTER TABLE amendment_documents
    ADD COLUMN IF NOT EXISTS text_body       TEXT,
    ADD COLUMN IF NOT EXISTS body_html       TEXT,
    ADD COLUMN IF NOT EXISTS body_fetched_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_amendment_documents_has_body
    ON amendment_documents ((text_body IS NOT NULL));

COMMENT ON COLUMN amendment_documents.text_body IS
    'Plain-text body extracted from the doceo .docx manifestation. Populated '
    'by backfill_amendment_documents_body.py; null when never fetched or when '
    'the DOCX itself is empty/missing.';
COMMENT ON COLUMN amendment_documents.body_html IS
    'HTML body composed from the DOCX paragraphs (one <p> per paragraph). '
    'Lighter than the raw DOCX XML; useful when partners want to render the '
    'opinion in-browser.';
COMMENT ON COLUMN amendment_documents.body_fetched_at IS
    'Timestamp of the last successful DOCX fetch. Null when never fetched.';
