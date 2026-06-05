-- Migration 110 — EP eMeeting committee agendas (API v2 "European Parliament" folder)
--
-- Backing store for the /emeeting endpoint. The European Parliament's eMeeting
-- feature (emeeting.europarl.europa.eu) is a SPA over an OPEN JSON API (no WAF):
--   organs/committees -> agenda/agendaArchive?organ={CODE} -> OJ/oj?reference={ref}
-- Each committee OJ (agenda) carries items, each item a procedure (OEIL ref),
-- rapporteur actors, and document sets (draft reports PR, amendments AM, voting
-- lists / compromise amendments DV) with multi-language PDF links on the
-- un-walled www.europarl.europa.eu/meetdocs store.
--
-- One row per committee OJ. The full item/document tree is stored in `items`
-- (JSONB) so the detail endpoint exposes everything; `procedure_refs` and
-- `rapporteurs` are denormalised for filtering + MEUB anchor linking. Bodies are
-- composed at ingest time, so the API never calls eMeeting on the request path.
--
-- Public reference data: anon + authenticated SELECT, service_role ALL. Re-runnable.

BEGIN;

CREATE TABLE IF NOT EXISTS ep_emeeting_agendas (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    oj_reference      TEXT NOT NULL UNIQUE,      -- 'AFCO(2026)0505_1'

    committee_code    TEXT NOT NULL,             -- 'AFCO'
    committee_name    TEXT,                       -- 'Committee on Constitutional Affairs'
    meeting_date      DATE,
    meeting_reference TEXT,

    title             TEXT NOT NULL,
    public_url        TEXT,                       -- agenda PDF or eMeeting timeline
    body_txt          TEXT,                       -- always filled (composed from the agenda)
    body_html         TEXT,
    agenda_pdf_url    TEXT,                       -- the OJ agenda document PDF (EN)

    items             JSONB DEFAULT '[]'::jsonb,  -- full item/document tree
    procedure_refs    TEXT[] DEFAULT '{}',        -- OEIL refs on the agenda (MEUB anchor)
    rapporteurs       TEXT[] DEFAULT '{}',        -- 'Loránt Vincze (PPE)'
    document_count    INTEGER DEFAULT 0,
    event_reference   TEXT,                       -- ties to a calendar event

    source_url        TEXT,
    first_seen        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_emeeting_committee ON ep_emeeting_agendas (committee_code);
CREATE INDEX IF NOT EXISTS ix_emeeting_date      ON ep_emeeting_agendas (meeting_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS ix_emeeting_procrefs  ON ep_emeeting_agendas USING GIN (procedure_refs);

ALTER TABLE ep_emeeting_agendas ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ep_emeeting_public_read ON ep_emeeting_agendas;
CREATE POLICY ep_emeeting_public_read ON ep_emeeting_agendas
    FOR SELECT TO anon, authenticated USING (true);

GRANT SELECT ON ep_emeeting_agendas TO anon, authenticated;
GRANT ALL ON ep_emeeting_agendas TO service_role;

COMMIT;
