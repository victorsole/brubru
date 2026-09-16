-- 233_infringement_register.sql
-- The European Commission's register of infringement decisions, and the cases they belong to.
--
-- WHY
-- ---
-- /api/v2/commission/infringements served 169 Commission press releases about
-- infringements (166 of them undated, last ingested 7 May 2026). The Commission's own
-- register holds every decision it has adopted in infringement procedures since 1987:
-- 62,610 decisions across 25,658 cases on 16 Sep 2026, 1,909 cases still active. It is
-- served as JSON by the register behind
-- ec.europa.eu/implementing-eu-law/search-infringement-decisions/ (POST api/decisions),
-- over plain HTTP.
--
-- WHAT
-- ----
-- infringement_decisions: one row per decision, keyed as the register keys it
--   (infringement number, decision date, decision type), unique on all 62,610 rows.
-- infringement_cases: one row per infringement number, rebuilt from its decisions by
--   scripts/sync_infringement_register.py (latest decision, counts, links).
-- Both carry the five Brubru datapoints (public_url, body_txt, body_html, document_date
-- via decision_date / latest_decision_date, creation_date) and body_source.
--
-- public_url: the register has no page per case or decision (its search app ignores
-- every URL parameter; tested 16 Sep 2026). A decision links to its own press release,
-- memo or Court case when it has one; otherwise to the register search page, and
-- public_url_kind says which, so nobody mistakes a search page for the item.

CREATE TABLE IF NOT EXISTS public.infringement_decisions (
    id                   bigserial   PRIMARY KEY,
    infringement_number  text        NOT NULL,
    member_state         text,                  -- the register's code (EL = Greece, UK)
    member_state_name    text,
    lead_dg              text,
    lead_dg_code         text,
    case_type            text,                  -- Non-communication | Bad application | ...
    title                text,
    active_case          boolean,
    non_communication    boolean,
    decision_date        date        NOT NULL,
    decision_type        text        NOT NULL,
    decision_type_code   text,
    decision_category    text,                  -- LFN | RO | RTC | CLOSURES | ...
    press_release        text,
    press_release_url    text,
    memo                 text,
    memo_url             text,
    court_case           text,
    court_case_url       text,
    policy_areas         text[]      NOT NULL DEFAULT '{}',
    public_url           text,
    public_url_kind      text,                  -- press_release | memo | court_case | register_search
    body_txt             text,
    body_html            text,
    body_source          text,
    creation_date        timestamptz NOT NULL DEFAULT now(),
    last_seen_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT infringement_decisions_natural_key UNIQUE (infringement_number, decision_date, decision_type)
);

CREATE INDEX IF NOT EXISTS ix_infringement_decisions_number ON public.infringement_decisions (infringement_number);
CREATE INDEX IF NOT EXISTS ix_infringement_decisions_date ON public.infringement_decisions (decision_date DESC, id DESC);
CREATE INDEX IF NOT EXISTS ix_infringement_decisions_member_state ON public.infringement_decisions (member_state, decision_date DESC);

CREATE TABLE IF NOT EXISTS public.infringement_cases (
    id                        bigserial   PRIMARY KEY,
    infringement_number       text        NOT NULL UNIQUE,
    member_state              text,
    member_state_name         text,
    lead_dg                   text,
    lead_dg_code              text,
    case_type                 text,
    title                     text,
    active_case               boolean,
    non_communication         boolean,
    first_decision_date       date,
    latest_decision_date      date,
    latest_decision_type      text,
    latest_decision_category  text,
    decision_count            integer     NOT NULL DEFAULT 0,
    policy_areas              text[]      NOT NULL DEFAULT '{}',
    court_cases               text[]      NOT NULL DEFAULT '{}',
    press_release_urls        text[]      NOT NULL DEFAULT '{}',
    public_url                text,
    public_url_kind           text,
    body_txt                  text,
    body_html                 text,
    body_source               text,
    creation_date             timestamptz NOT NULL DEFAULT now(),
    last_seen_at              timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_infringement_cases_latest ON public.infringement_cases (latest_decision_date DESC, id DESC);
CREATE INDEX IF NOT EXISTS ix_infringement_cases_member_state ON public.infringement_cases (member_state, latest_decision_date DESC);
CREATE INDEX IF NOT EXISTS ix_infringement_cases_active ON public.infringement_cases (active_case) WHERE active_case;

ALTER TABLE public.infringement_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.infringement_cases ENABLE ROW LEVEL SECURITY;

-- Public records: read for everyone, writes by service_role only.
DROP POLICY IF EXISTS infringement_decisions_read ON public.infringement_decisions;
CREATE POLICY infringement_decisions_read ON public.infringement_decisions
    FOR SELECT TO anon, authenticated USING (true);
DROP POLICY IF EXISTS infringement_decisions_service_all ON public.infringement_decisions;
CREATE POLICY infringement_decisions_service_all ON public.infringement_decisions
    FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS infringement_cases_read ON public.infringement_cases;
CREATE POLICY infringement_cases_read ON public.infringement_cases
    FOR SELECT TO anon, authenticated USING (true);
DROP POLICY IF EXISTS infringement_cases_service_all ON public.infringement_cases;
CREATE POLICY infringement_cases_service_all ON public.infringement_cases
    FOR ALL TO service_role USING (true) WITH CHECK (true);

GRANT SELECT ON public.infringement_decisions TO anon, authenticated;
GRANT ALL    ON public.infringement_decisions TO service_role;
GRANT SELECT ON public.infringement_cases TO anon, authenticated;
GRANT ALL    ON public.infringement_cases TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.infringement_decisions_id_seq TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.infringement_cases_id_seq TO service_role;
