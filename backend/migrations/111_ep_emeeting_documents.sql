-- Migration 111 — EP eMeeting documents (document-level, sibling to migration 110)
--
-- migration 110 stores one row per committee AGENDA (items/documents nested in
-- JSONB). This table makes every DOCUMENT first-class: one row per document
-- attached to an agenda item (draft reports PR, amendments AM, voting lists /
-- compromise amendments DV, reports RR, opinions AD, agendas OJ, minutes PV...),
-- with ALL language PDF URLs (up to ~24) and the linking anchors (committee,
-- meeting date, OEIL procedure ref, rapporteurs, dossier).
--
-- This is the "many more PDF documents" feed — there are ~15-20 documents per
-- agenda, each with up to 24 language PDFs on the un-walled meetdocs store.
--
-- Public reference data: anon + authenticated SELECT, service_role ALL. Re-runnable.

BEGIN;

CREATE TABLE IF NOT EXISTS ep_emeeting_documents (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_key       TEXT NOT NULL UNIQUE,     -- '{oj_reference}::{visual_reference|gepro:reference}'

    gepro_code         TEXT,                      -- PR | AM | DV | RR | AD | OJ | PV ...
    gepro_description  TEXT,                      -- 'Draft report / Draft recommendation'
    doc_kind           TEXT,                      -- normalised: draft_report | amendment | voting_list
                                                  -- | compromise_amendments | agenda | minutes | report | opinion | ...
    reference          TEXT,                      -- 'PE787.766'
    visual_reference   TEXT,                      -- 'PR-PE784.388'
    title              TEXT,

    committee_code     TEXT,
    committee_name     TEXT,
    meeting_date       DATE,
    oj_reference       TEXT,                      -- the agenda this doc sits on
    agenda_id          UUID,                      -- ep_emeeting_agendas.id (resolved at ingest)
    dossier_reference  TEXT,                      -- 'AFCO/10/05162'
    procedure_ref      TEXT,                      -- OEIL ref (MEUB anchor)
    item_title         TEXT,                      -- the agenda item the doc belongs to
    document_set_type  TEXT,                      -- RAP | OTH | ...
    rapporteurs        TEXT[] DEFAULT '{}',

    pdf_url            TEXT,                      -- EN (or first) PDF — the public_url
    pdf_urls           JSONB DEFAULT '{}'::jsonb, -- {lang_code: url} ALL languages
    languages          TEXT[] DEFAULT '{}',

    body_txt           TEXT,
    body_html          TEXT,
    source_url         TEXT,
    first_seen         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetched_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_emeetingdoc_gepro     ON ep_emeeting_documents (gepro_code);
CREATE INDEX IF NOT EXISTS ix_emeetingdoc_kind      ON ep_emeeting_documents (doc_kind);
CREATE INDEX IF NOT EXISTS ix_emeetingdoc_committee ON ep_emeeting_documents (committee_code);
CREATE INDEX IF NOT EXISTS ix_emeetingdoc_date      ON ep_emeeting_documents (meeting_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS ix_emeetingdoc_proc      ON ep_emeeting_documents (procedure_ref);
CREATE INDEX IF NOT EXISTS ix_emeetingdoc_oj        ON ep_emeeting_documents (oj_reference);

ALTER TABLE ep_emeeting_documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ep_emeeting_documents_public_read ON ep_emeeting_documents;
CREATE POLICY ep_emeeting_documents_public_read ON ep_emeeting_documents
    FOR SELECT TO anon, authenticated USING (true);

GRANT SELECT ON ep_emeeting_documents TO anon, authenticated;
GRANT ALL ON ep_emeeting_documents TO service_role;

COMMIT;
