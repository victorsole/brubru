-- 251: Commission follow-up to European Parliament adopted texts (EP Open Data SP documents).
--
-- /api/v2/external-documents publishes ACT_FOLLOWUP records: what the Commission says it
-- will do about a resolution Parliament adopted. We held none of them, and no other source
-- we ingest carries the link from an adopted text to the Commission's answer. Identifiers
-- look like SP-2026-04-14-TA-10-2025-0343, which names both the follow-up date and the
-- adopted text it answers.
--
-- Body text is fetched from the EN manifestation (DOCX) the API lists, the same way
-- parliamentary-question answers are. A document whose body we have not read keeps NULL
-- rather than a title repeated as a body.
--
-- Deep offsets on this endpoint TIME OUT (EP's own open issue #28): offset 1,000 and 3,000
-- answer, 4,000 and 6,000 do not. The ingest therefore partitions by year instead of paging
-- to the end, which is why identifier_year is stored and indexed.

DROP TABLE IF EXISTS public.ep_external_documents;
CREATE TABLE public.ep_external_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identifier      TEXT        NOT NULL UNIQUE,
    work_type       TEXT,
    document_date   DATE,
    identifier_year INTEGER,
    title           TEXT,
    answers_to      TEXT[],
    creator         TEXT,
    public_url      TEXT,
    file_url        TEXT,
    body_txt        TEXT,
    body_html       TEXT,
    body_source     TEXT,
    -- The trio every ingest table here uses, and which the API maps to the five
    -- datapoints: first_seen -> creation_date, last_updated -> the ?updated_from=
    -- change signal, scraped_at -> "is this feed alive". Matches rsb_opinions,
    -- texts_adopted, commission_documents, eprs_publications, transparency_meetings,
    -- tris_notifications and secondary_acts. created_at/updated_at would have been a
    -- third spelling for no reason.
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.ep_external_documents IS
    'EP Open Data /external-documents: Commission follow-up (SP) to adopted texts. '
    'One row per follow-up document; answers_to holds the adopted-text references it responds to.';
COMMENT ON COLUMN public.ep_external_documents.document_date IS
    'Read from the EP record, never derived from the identifier. NULL when EP does not state one.';
COMMENT ON COLUMN public.ep_external_documents.body_source IS
    'How the body was obtained, e.g. fetched:docx. NULL body means we have not read it, '
    'which is not the same as the document being empty.';

CREATE INDEX IF NOT EXISTS ix_ep_external_documents_year ON public.ep_external_documents (identifier_year);
CREATE INDEX IF NOT EXISTS ix_ep_external_documents_date ON public.ep_external_documents (document_date);
CREATE INDEX IF NOT EXISTS ix_ep_external_documents_updated ON public.ep_external_documents (last_updated);

ALTER TABLE public.ep_external_documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ep_external_documents_read ON public.ep_external_documents;
CREATE POLICY ep_external_documents_read ON public.ep_external_documents
    FOR SELECT USING (true);

DROP POLICY IF EXISTS ep_external_documents_service ON public.ep_external_documents;
CREATE POLICY ep_external_documents_service ON public.ep_external_documents
    FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

-- The default grant was removed on 30 Oct 2026, so a replay without these is unreadable.
GRANT SELECT ON public.ep_external_documents TO anon, authenticated;
GRANT ALL    ON public.ep_external_documents TO service_role;

-- updated_at is a change signal: it must move only when content changes, or an incremental
-- caller re-reads the corpus every night. Same guard as migrations 245-249.
DROP TRIGGER IF EXISTS trg_ep_external_documents_touch ON public.ep_external_documents;
CREATE TRIGGER trg_ep_external_documents_touch
    BEFORE UPDATE ON public.ep_external_documents
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed(
        'last_updated', 'scraped_at', 'first_seen');
