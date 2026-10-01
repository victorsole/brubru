-- 265: EU sanctions listings read from the Official Journal (the gap after the Commission list).
--
-- The Commission's consolidated financial sanctions list (eu_sanctions, migration 055) was
-- last published on 22 September 2026 and carries no legal act newer than 23 July 2026,
-- in every format and in its own RSS feed. Restrictive-measures regulations published in
-- the OJ after that date add, delete, replace and amend listings that the list does not
-- yet show. This table holds those entries, read from each act's annex (Cellar XHTML).
--
-- One row per entry per act. The identity is the act's CELEX, the annex block and the
-- entry's position in it, all read from the source; nothing is derived. body_txt is the
-- full text of the source row and is the evidence; name is a parsed convenience.
-- Only regulations are read: the paired CFSP decision repeats the same entries.

CREATE TABLE IF NOT EXISTS public.eu_sanctions_oj_delta (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_key         TEXT NOT NULL UNIQUE,          -- '<celex>#<block>#<position>'
    celex             TEXT NOT NULL,
    act_title         TEXT,
    document_date     DATE,                          -- the act's date (Cellar)
    base_regulation   TEXT,                          -- e.g. '269/2014', read from the act
    annex             TEXT,                          -- e.g. 'I', 'IX'
    action            TEXT NOT NULL CHECK (action IN
                        ('added', 'deleted', 'replaced', 'amended', 'list_replaced')),
    heading           TEXT,                          -- the lead sentence of the annex block
    subject_type      CHAR(1) CHECK (subject_type IN ('P', 'E', 'V')),
    entry_number      TEXT,
    name              TEXT,
    identifying_info  TEXT,
    reasons           TEXT,
    date_of_listing   DATE,
    public_url        TEXT,
    body_txt          TEXT NOT NULL,
    body_html         TEXT,
    body_source       TEXT,
    first_seen        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scraped_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.eu_sanctions_oj_delta IS
    'Sanctions listings, delistings and amendments read from OJ regulations published after '
    'the newest act in the Commission consolidated list (eu_sanctions). Superseded once the '
    'Commission list catches up; the daily job reports the gap.';

CREATE INDEX IF NOT EXISTS ix_eu_sanctions_oj_delta_celex   ON public.eu_sanctions_oj_delta (celex);
CREATE INDEX IF NOT EXISTS ix_eu_sanctions_oj_delta_date    ON public.eu_sanctions_oj_delta (document_date DESC);
CREATE INDEX IF NOT EXISTS ix_eu_sanctions_oj_delta_base    ON public.eu_sanctions_oj_delta (base_regulation);
CREATE INDEX IF NOT EXISTS ix_eu_sanctions_oj_delta_updated ON public.eu_sanctions_oj_delta (last_updated);
CREATE INDEX IF NOT EXISTS ix_eu_sanctions_oj_delta_name
    ON public.eu_sanctions_oj_delta USING gin (to_tsvector('simple', COALESCE(name, '') || ' ' || body_txt));

ALTER TABLE public.eu_sanctions_oj_delta ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS eu_sanctions_oj_delta_read ON public.eu_sanctions_oj_delta;
CREATE POLICY eu_sanctions_oj_delta_read ON public.eu_sanctions_oj_delta
    FOR SELECT USING (true);

DROP POLICY IF EXISTS eu_sanctions_oj_delta_service ON public.eu_sanctions_oj_delta;
CREATE POLICY eu_sanctions_oj_delta_service ON public.eu_sanctions_oj_delta
    FOR ALL USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

GRANT SELECT ON public.eu_sanctions_oj_delta TO anon, authenticated;
GRANT ALL    ON public.eu_sanctions_oj_delta TO service_role;

DROP TRIGGER IF EXISTS trg_eu_sanctions_oj_delta_touch ON public.eu_sanctions_oj_delta;
CREATE TRIGGER trg_eu_sanctions_oj_delta_touch
    BEFORE UPDATE ON public.eu_sanctions_oj_delta
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed(
        'last_updated', 'scraped_at', 'first_seen');
