-- 263: procurement_documents: the files attached to an EU procurement procedure, with their text.
--
-- API audit, 30 Sep 2026 (Victor approved "Part A"): the agency procurement routes carried
-- no document at all, while Cedefop alone publishes 1,579 files on 360 of its 464 procedure
-- pages (specifications, forms, Q&A, corrigenda, award notices; PDF, ZIP, DOC, DOCX, XLS,
-- XLSX). One row per file; a file inside a ZIP is its own row, pointing at the archive.
-- The text is extracted and stored; the binary is not.
--
-- Served under each procurement item: /api/v2/funding/{body}-tenders/{id}/documents.
-- Columns follow ep_external_documents (migration 251), the most recent document table:
-- body_txt / body_html / body_source and the first_seen / last_updated / scraped_at trio.

CREATE TABLE IF NOT EXISTS public.procurement_documents (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    economy_item_id  BIGINT      NOT NULL REFERENCES public.economy_items(id) ON DELETE CASCADE,
    body_code        TEXT        NOT NULL,
    tender_reference TEXT,
    title            TEXT,
    file_url         TEXT        NOT NULL,
    parent_file_url  TEXT,
    file_name        TEXT,
    file_format      TEXT,
    file_size        BIGINT,
    language         TEXT,
    document_date    DATE,
    public_url       TEXT,
    body_txt         TEXT,
    body_html        TEXT,
    body_source      TEXT,
    first_seen       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scraped_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (economy_item_id, file_url)
);

COMMENT ON TABLE public.procurement_documents IS
    'Files attached to an EU procurement procedure (economy_items procurement rows), one row per file, '
    'with extracted text. A file inside a ZIP is its own row; parent_file_url is the archive.';
COMMENT ON COLUMN public.procurement_documents.file_url IS
    'Address of the file. For a file inside a ZIP: the archive address + "#" + the path inside it.';
COMMENT ON COLUMN public.procurement_documents.document_date IS
    'The date the publisher shows next to the file, when it shows one. NULL otherwise, never derived.';
COMMENT ON COLUMN public.procurement_documents.body_source IS
    'How the text was obtained: extracted:pdf, extracted:docx, extracted:doc, extracted:xlsx, extracted:xls, '
    'or no-text:<reason> (e.g. a scanned PDF). NULL body with no-text means read and empty, not unread.';

CREATE INDEX IF NOT EXISTS ix_procurement_documents_item ON public.procurement_documents (economy_item_id);
CREATE INDEX IF NOT EXISTS ix_procurement_documents_body ON public.procurement_documents (body_code);
CREATE INDEX IF NOT EXISTS ix_procurement_documents_updated ON public.procurement_documents (last_updated);

ALTER TABLE public.procurement_documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS procurement_documents_read ON public.procurement_documents;
CREATE POLICY procurement_documents_read ON public.procurement_documents
    FOR SELECT USING (true);

DROP POLICY IF EXISTS procurement_documents_service ON public.procurement_documents;
CREATE POLICY procurement_documents_service ON public.procurement_documents
    FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

GRANT SELECT ON public.procurement_documents TO anon, authenticated;
GRANT ALL    ON public.procurement_documents TO service_role;

-- last_updated is a change signal: it moves only when content changes (migration 245 guard).
DROP TRIGGER IF EXISTS trg_procurement_documents_touch ON public.procurement_documents;
CREATE TRIGGER trg_procurement_documents_touch
    BEFORE UPDATE ON public.procurement_documents
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed(
        'last_updated', 'scraped_at', 'first_seen');
