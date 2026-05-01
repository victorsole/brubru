-- 046_add_infringements_and_funds_tenders.sql
--
-- Two new collections requested for the GovClipping partnership.
--
-- Source-URL discipline (post 1 May 2026 fixture incident):
--   Every row MUST have a source_url that is row-specific (not a listing
--   page). Backfill scripts that hit a real upstream source only — no
--   curated seeds. The audit_url_legitimacy.py checker will flag any
--   table where every row shares a placeholder URL.

-- ============================================================================
-- 1. infringement_procedures
--    Source: ec.europa.eu/commission/presscorner (the monthly INF/yy/nnnn
--    decision packages: letters of formal notice, reasoned opinions,
--    referrals to the Court of Justice, closures).
-- ============================================================================
CREATE TABLE IF NOT EXISTS infringement_procedures (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Press-release reference (INF/25/4001 form) is the canonical EC ID.
    inf_reference     VARCHAR(40) NOT NULL UNIQUE,
    -- ISO-3166 alpha-2 of the addressed Member State (or 'EU' for general).
    member_state      CHAR(2),
    -- Stage of the procedure: letter of formal notice / reasoned opinion /
    -- referral / closure / additional letter / additional reasoned opinion.
    procedure_stage   VARCHAR(64),
    sector            VARCHAR(120),
    title             TEXT NOT NULL,
    summary           TEXT,
    decision_date     DATE,
    -- Press-release URL on presscorner — row-specific, e.g.
    -- https://ec.europa.eu/commission/presscorner/detail/en/INF_25_4001
    source_url        TEXT NOT NULL,
    pdf_url           TEXT,
    related_celex     TEXT[] DEFAULT '{}'::TEXT[],
    policy_areas      TEXT[] DEFAULT '{}'::TEXT[],
    is_test           BOOLEAN NOT NULL DEFAULT FALSE,
    scraped_at        TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    last_updated      TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_inf_member_state ON infringement_procedures (member_state);
CREATE INDEX IF NOT EXISTS ix_inf_decision_date ON infringement_procedures (decision_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS ix_inf_stage ON infringement_procedures (procedure_stage);
CREATE INDEX IF NOT EXISTS ix_inf_test ON infringement_procedures (is_test) WHERE is_test = FALSE;

ALTER TABLE infringement_procedures ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all_infringement" ON infringement_procedures
    FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "authenticated_read_infringement" ON infringement_procedures
    FOR SELECT TO authenticated USING (TRUE);

COMMENT ON TABLE infringement_procedures IS
    'Commission infringement procedure decisions. Source: presscorner INF references. is_test column lets the API filter out fixtures.';
COMMENT ON COLUMN infringement_procedures.is_test IS
    'TRUE for synthetic / fixture rows. API queries MUST filter is_test=FALSE.';

-- ============================================================================
-- 2. funding_opportunities
--    Source: ec.europa.eu/info/funding-tenders/opportunities/portal — calls
--    for proposals across all EU programmes (Horizon Europe, Digital Europe,
--    CEF, EU4Health, Erasmus+, Citizens-Equality-Rights-Values, etc).
-- ============================================================================
CREATE TABLE IF NOT EXISTS funding_opportunities (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Topic / call ID assigned by the portal (e.g. HORIZON-CL3-2026-01-CS-01).
    topic_id          VARCHAR(120) NOT NULL UNIQUE,
    call_id           VARCHAR(120),
    programme         VARCHAR(120),
    title             TEXT NOT NULL,
    short_summary     TEXT,
    description       TEXT,
    -- Status: open / forthcoming / closed / under-evaluation.
    status            VARCHAR(40),
    type_of_action    VARCHAR(80),
    -- Deadlines: many calls are single-stage; some are two-stage with
    -- different first/second deadlines.
    deadline          TIMESTAMP WITHOUT TIME ZONE,
    deadline_secondary TIMESTAMP WITHOUT TIME ZONE,
    -- Indicative budget in EUR (millions allowed).
    indicative_budget NUMERIC(20, 2),
    budget_currency   VARCHAR(8) DEFAULT 'EUR',
    -- Row-specific URL on the funding portal:
    -- https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/{topic_id}
    source_url        TEXT NOT NULL,
    documents_url     TEXT,
    keywords          TEXT[] DEFAULT '{}'::TEXT[],
    target_audience   TEXT[] DEFAULT '{}'::TEXT[],
    is_test           BOOLEAN NOT NULL DEFAULT FALSE,
    published_at      TIMESTAMP WITHOUT TIME ZONE,
    last_updated      TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    scraped_at        TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_fund_status ON funding_opportunities (status);
CREATE INDEX IF NOT EXISTS ix_fund_deadline ON funding_opportunities (deadline);
CREATE INDEX IF NOT EXISTS ix_fund_programme ON funding_opportunities (programme);
CREATE INDEX IF NOT EXISTS ix_fund_test ON funding_opportunities (is_test) WHERE is_test = FALSE;

ALTER TABLE funding_opportunities ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all_funding" ON funding_opportunities
    FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "authenticated_read_funding" ON funding_opportunities
    FOR SELECT TO authenticated USING (TRUE);

COMMENT ON TABLE funding_opportunities IS
    'EU funding calls aggregated from the funding-tenders portal.';
COMMENT ON COLUMN funding_opportunities.is_test IS
    'TRUE for synthetic / fixture rows. API queries MUST filter is_test=FALSE.';
