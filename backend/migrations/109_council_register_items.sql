-- Migration 109 — Council of the EU register cache (API v2 "Council of the EU" folder)
--
-- Backing store for the 8 new Council-of-the-EU API endpoints that have no
-- pre-existing table:
--   council-meetings, council-voting-results, council-register,
--   council-oj-agendas, council-preparatory-bodies, council-press-releases,
--   council-research-papers, council-treaties-agreements
--
-- One generic table with a `content_type` discriminator — every Council
-- surface on consilium.europa.eu is the same shape (a dated, titled item with
-- a public URL and a body), so one table + one scraper serves all eight.
-- Bodies (body_txt / body_html) are composed at scrape time from the real
-- inline facts (or the un-walled data.consilium PDF text) and stored here, so
-- the API never scrapes on the request path and the 5 mandatory datapoints are
-- always present.
--
-- Public reference data: anon + authenticated SELECT, service_role ALL.
-- Safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS council_register_items (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_key               TEXT NOT NULL UNIQUE,   -- '<content_type>:<ref-or-url-slug>' dedup key

    content_type           TEXT NOT NULL,          -- meeting | voting_result | register_doc | oj_agenda
                                                    -- | preparatory_body | press_release | research_paper | treaty_agreement
    title                  TEXT NOT NULL,
    public_url             TEXT,                   -- canonical citizen URL (consilium page or PDF)

    body_txt               TEXT,                   -- always filled (composed from real facts or PDF text)
    body_html              TEXT,                   -- always filled (composed; null only for honest PDF-only rows)

    document_date          DATE,                   -- meeting/publication date
    document_ref           TEXT,                   -- 'ST 9727 2026 INIT' / 'CM 3003 2026 INIT' where present
    council_configuration  TEXT,                   -- GAC/FAC/ECOFIN/... where applicable
    interinstitutional_ref TEXT,                   -- e.g. '2021/0297(COD)' -> OEIL join
    subject_matters        TEXT[] DEFAULT '{}',    -- e.g. {INF,VOTE,CODEC,PUBLIC}
    pdf_url                TEXT,                   -- data.consilium.europa.eu/.../pdf (un-walled) where present
    policy_areas           TEXT[] DEFAULT '{}',

    source_url             TEXT,                   -- the consilium index page this row was scraped from
    extra                  JSONB DEFAULT '{}'::jsonb,

    first_seen             TIMESTAMPTZ NOT NULL DEFAULT NOW(),  -- creation_date datapoint
    fetched_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_council_register_type      ON council_register_items (content_type);
CREATE INDEX IF NOT EXISTS ix_council_register_date      ON council_register_items (document_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS ix_council_register_config    ON council_register_items (council_configuration);
CREATE INDEX IF NOT EXISTS ix_council_register_interinst ON council_register_items (interinstitutional_ref);

ALTER TABLE council_register_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS council_register_public_read ON council_register_items;
CREATE POLICY council_register_public_read ON council_register_items
    FOR SELECT TO anon, authenticated USING (true);

GRANT SELECT ON council_register_items TO anon, authenticated;
GRANT ALL ON council_register_items TO service_role;

COMMIT;
