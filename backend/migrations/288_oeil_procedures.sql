-- 288: oeil_procedures, every OEIL procedure file the URL probe has found (9 Oct 2026).
--
-- Why: /api/v2/parliament/resolution-procedures (ep_resolutions) is to hold EVERY INI, RSP and
-- INL procedure, debate-only RSPs included (Victor, 9 Oct 2026). Nothing Brubru held could say
-- which procedures exist: legislative_carriages misses whole blocks (all of 2026/2560-2576; 30
-- RSPs for 2025), and ep_resolutions only ever gained adopted texts plus a one-off batch of 34
-- rows on 6 Mar 2026. OEIL serves one page per procedure, found by asking for its URL
-- (services/scrapers/oeil_probe.py, built by the Superscraper session).
--
-- One row per procedure page OEIL has served. A page that later answers OEIL's own 404 message
-- is never deleted: `served` turns false and `unserved_since` keeps when, because a 404 can mean
-- "being initiated" as much as "gone". Writer: scripts/sync_oeil_procedures.py, and only it.
-- Readers: the resolutions corpus job (INI/RSP/INL rows), audits.
BEGIN;

CREATE TABLE IF NOT EXISTS public.oeil_procedures (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    procedure_ref    TEXT        NOT NULL UNIQUE,              -- 'YYYY/NNNN(TYPE)', exactly as OEIL serves it
    procedure_year   INTEGER     NOT NULL,
    procedure_number INTEGER     NOT NULL,
    procedure_type   TEXT        NOT NULL,                     -- the three letters in the reference
    title            TEXT,
    type_label       TEXT,                                     -- 'Resolutions on topical subjects', ...
    instrument       TEXT,                                     -- line under the type (Regulation, Directive, ...)
    subject          TEXT,
    oeil_status      TEXT,                                     -- OEIL's status line, verbatim
    key_events       JSONB       NOT NULL DEFAULT '[]'::jsonb, -- [{date, event, reference}] from the Key events table
    motion_refs      TEXT[]      NOT NULL DEFAULT '{}',        -- B10-/RC-B10- references on the page
    text_refs        TEXT[]      NOT NULL DEFAULT '{}',        -- T10- references on the page
    public_url       TEXT        NOT NULL,
    served           BOOLEAN     NOT NULL DEFAULT true,
    last_served_at   TIMESTAMPTZ NOT NULL DEFAULT now(),      -- last time OEIL answered 200 for it
    unserved_since   TIMESTAMPTZ,                              -- first 404 after being served; NULL while served
    first_seen       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated     TIMESTAMPTZ NOT NULL DEFAULT now(),
    scraped_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT oeil_procedures_ref_parts CHECK (
        procedure_ref = procedure_year::text || '/' || lpad(procedure_number::text, 4, '0') || '(' || procedure_type || ')')
);

CREATE INDEX IF NOT EXISTS idx_oeil_procedures_type_year ON public.oeil_procedures (procedure_type, procedure_year);
CREATE INDEX IF NOT EXISTS idx_oeil_procedures_scraped ON public.oeil_procedures (scraped_at);

ALTER TABLE public.oeil_procedures ENABLE ROW LEVEL SECURITY;
CREATE POLICY oeil_procedures_public_read ON public.oeil_procedures
    FOR SELECT TO anon, authenticated USING (true);
GRANT SELECT ON public.oeil_procedures TO anon, authenticated;
GRANT ALL ON public.oeil_procedures TO service_role;

-- last_updated moves only when the content changes; a re-read that finds the same page does not.
CREATE TRIGGER trg_oeil_procedures_touch BEFORE UPDATE ON public.oeil_procedures
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at,last_served_at', 'first_seen');

COMMENT ON TABLE public.oeil_procedures IS
    'Every OEIL procedure page the URL probe has found. Never deleted: a page that stops answering gets served=false. Writer: scripts/sync_oeil_procedures.py.';

COMMIT;
