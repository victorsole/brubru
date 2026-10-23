-- 310: ft_cascade_calls, the Funding & Tenders Portal's calls for funding in cascade (23 Oct 2026).
--
-- EU-funded projects issue open calls of their own (financial support to third parties); the
-- portal lists them under its calls for proposals as "Calls for funding in cascade (issued by
-- funded projects)" and files each one under the identifier of the topic that funds it. Brubru
-- kept one row per identifier in ft_calls_for_proposals, so a topic and its cascade calls merged
-- into one row: census of 23 Oct, 1,420 cascade calls under 285 topics (up to 102 under one),
-- 111 of our topic rows carrying a cascade call's dates, none held as itself. Each cascade call
-- has its own number at the portal (`callccm2Id`, its page competitive-calls-cs/<number>), so it
-- gets its own row here, keyed on that number. Structure follows ft_calls_for_proposals for the
-- shared fields and the first_seen / last_updated / scraped_at trio of the newer tables (288).

CREATE TABLE IF NOT EXISTS public.ft_cascade_calls (
    id                  BIGSERIAL PRIMARY KEY,
    call_id             TEXT        NOT NULL UNIQUE,   -- the portal's call number (callccm2Id)
    topic_id            TEXT,                          -- the topic that funds it (the record's identifier)
    title               TEXT        NOT NULL,          -- the call's own title (callTitle)
    topic_title         TEXT,                          -- the funding topic's title (the record's title)
    project_id          TEXT,                          -- grant agreement number of the issuing project
    project_acronym     TEXT,
    project_name        TEXT,
    framework_programme TEXT,
    status              TEXT,                          -- forthcoming | open | closed, from its own dates
    deadline_model      TEXT,                          -- single-stage | multiple cut-off | ...
    published_at        TIMESTAMPTZ,                   -- the portal's "Opening date/Publication date"
    deadline            TIMESTAMPTZ,                   -- the next (or last) cut-off
    deadline_secondary  TIMESTAMPTZ,                   -- the final cut-off, when later than `deadline`
    duration            TEXT,
    indicative_budget   NUMERIC,                       -- "Total funding available"
    budget_currency     TEXT        DEFAULT 'EUR',
    source_url          TEXT        NOT NULL,          -- the portal's page for this call
    description         TEXT,                          -- the page's text, sections as plain text
    description_html    TEXT,                          -- the same sections as HTML
    raw                 JSONB,                         -- the source record (not served)
    is_test             BOOLEAN     NOT NULL DEFAULT false,
    first_seen          TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated        TIMESTAMPTZ NOT NULL DEFAULT now(),
    scraped_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ft_cascade_calls_topic ON public.ft_cascade_calls (topic_id);
CREATE INDEX IF NOT EXISTS idx_ft_cascade_calls_project ON public.ft_cascade_calls (project_id);
CREATE INDEX IF NOT EXISTS idx_ft_cascade_calls_status ON public.ft_cascade_calls (status);
CREATE INDEX IF NOT EXISTS idx_ft_cascade_calls_deadline ON public.ft_cascade_calls (deadline);
CREATE INDEX IF NOT EXISTS idx_ft_cascade_calls_published ON public.ft_cascade_calls (published_at DESC NULLS LAST, id DESC);
CREATE INDEX IF NOT EXISTS idx_ft_cascade_calls_updated ON public.ft_cascade_calls (last_updated, id);
CREATE INDEX IF NOT EXISTS idx_ft_cascade_calls_first_seen ON public.ft_cascade_calls (first_seen, id);

ALTER TABLE public.ft_cascade_calls ENABLE ROW LEVEL SECURITY;
CREATE POLICY ft_cascade_calls_public_read ON public.ft_cascade_calls
    FOR SELECT TO anon, authenticated USING (true);
-- The schema's default privileges give anon and authenticated every privilege on a new table;
-- this one is read-only for them (RLS allows SELECT only, but the grants say so too).
REVOKE ALL ON public.ft_cascade_calls FROM anon, authenticated;
GRANT SELECT ON public.ft_cascade_calls TO anon, authenticated;
GRANT ALL ON public.ft_cascade_calls TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.ft_cascade_calls_id_seq TO service_role;

-- last_updated moves only when served content changes; a daily re-read that finds the same call
-- does not move it (scraped_at and the source copy are bookkeeping).
CREATE TRIGGER trg_ft_cascade_calls_touch BEFORE UPDATE ON public.ft_cascade_calls
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at,raw', 'first_seen');
