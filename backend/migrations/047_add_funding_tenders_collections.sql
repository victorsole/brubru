-- 047_add_funding_tenders_collections.sql
--
-- Three new EU Funds & Tenders Portal collections (1 May 2026, post-Jordi
-- meeting). Source: ec.europa.eu/info/funding-tenders/opportunities/portal.
--
-- The portal is a fully SPA-rendered site with OIDC + Akamai WAF. Anonymous
-- REST/JSON access is blocked. Real-data ingestion requires browser
-- automation (Playwright headless). For now the tables are created and the
-- endpoints expose honest empty — better empty than fabricated.

-- ============================================================================
-- 1. ft_calls_for_proposals — open + forthcoming + closed funding calls
-- ============================================================================
CREATE TABLE IF NOT EXISTS ft_calls_for_proposals (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Topic / call identifier on the portal (e.g. HORIZON-CL3-2026-01-CS-01).
    topic_id          VARCHAR(120) NOT NULL UNIQUE,
    call_id           VARCHAR(120),
    framework_programme VARCHAR(120),  -- Horizon Europe, Erasmus+, EU4Health, ...
    title             TEXT NOT NULL,
    description       TEXT,
    -- Status enum from the portal: open / forthcoming / closed / under-evaluation.
    status            VARCHAR(40),
    type_of_action    VARCHAR(80),  -- RIA, IA, CSA, COFUND, ...
    deadline          TIMESTAMP WITHOUT TIME ZONE,
    deadline_secondary TIMESTAMP WITHOUT TIME ZONE,
    indicative_budget NUMERIC(20, 2),
    budget_currency   VARCHAR(8) DEFAULT 'EUR',
    -- Row-specific URL on the funding portal.
    source_url        TEXT NOT NULL,
    documents_url     TEXT,
    keywords          TEXT[] DEFAULT '{}'::TEXT[],
    target_audience   TEXT[] DEFAULT '{}'::TEXT[],
    is_test           BOOLEAN NOT NULL DEFAULT FALSE,
    published_at      TIMESTAMP WITHOUT TIME ZONE,
    last_updated      TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    scraped_at        TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_ftc_status ON ft_calls_for_proposals (status);
CREATE INDEX IF NOT EXISTS ix_ftc_deadline ON ft_calls_for_proposals (deadline);
CREATE INDEX IF NOT EXISTS ix_ftc_programme ON ft_calls_for_proposals (framework_programme);
CREATE INDEX IF NOT EXISTS ix_ftc_test ON ft_calls_for_proposals (is_test) WHERE is_test = FALSE;

ALTER TABLE ft_calls_for_proposals ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all_ft_calls" ON ft_calls_for_proposals
    FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "authenticated_read_ft_calls" ON ft_calls_for_proposals
    FOR SELECT TO authenticated USING (TRUE);

COMMENT ON TABLE ft_calls_for_proposals IS
    'EU funding calls for proposals from Funding & Tenders Portal. SPA-locked source — needs Playwright scraper.';


-- ============================================================================
-- 2. ft_calls_for_tenders — public-procurement opportunities
-- ============================================================================
CREATE TABLE IF NOT EXISTS ft_calls_for_tenders (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tender_reference  VARCHAR(120) NOT NULL UNIQUE,
    contracting_authority TEXT,
    title             TEXT NOT NULL,
    description       TEXT,
    contract_type     VARCHAR(60),  -- supply / service / works / public-private partnership
    status            VARCHAR(40),
    estimated_value   NUMERIC(20, 2),
    value_currency    VARCHAR(8) DEFAULT 'EUR',
    deadline          TIMESTAMP WITHOUT TIME ZONE,
    source_url        TEXT NOT NULL,
    documents_url     TEXT,
    cpv_codes         TEXT[] DEFAULT '{}'::TEXT[],
    is_test           BOOLEAN NOT NULL DEFAULT FALSE,
    published_at      TIMESTAMP WITHOUT TIME ZONE,
    last_updated      TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    scraped_at        TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_ftt_status ON ft_calls_for_tenders (status);
CREATE INDEX IF NOT EXISTS ix_ftt_deadline ON ft_calls_for_tenders (deadline);
CREATE INDEX IF NOT EXISTS ix_ftt_authority ON ft_calls_for_tenders (contracting_authority);
CREATE INDEX IF NOT EXISTS ix_ftt_test ON ft_calls_for_tenders (is_test) WHERE is_test = FALSE;

ALTER TABLE ft_calls_for_tenders ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all_ft_tenders" ON ft_calls_for_tenders
    FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "authenticated_read_ft_tenders" ON ft_calls_for_tenders
    FOR SELECT TO authenticated USING (TRUE);


-- ============================================================================
-- 3. ft_funded_projects — completed/active EU-funded grant projects
-- ============================================================================
CREATE TABLE IF NOT EXISTS ft_funded_projects (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id        VARCHAR(120) NOT NULL UNIQUE,  -- grant agreement number
    project_acronym   VARCHAR(120),
    title             TEXT NOT NULL,
    objective         TEXT,
    framework_programme VARCHAR(120),
    type_of_action    VARCHAR(80),
    coordinator_name  TEXT,
    coordinator_country CHAR(2),
    start_date        DATE,
    end_date          DATE,
    total_cost        NUMERIC(20, 2),
    eu_contribution   NUMERIC(20, 2),
    cost_currency     VARCHAR(8) DEFAULT 'EUR',
    status            VARCHAR(40),  -- ongoing / closed / terminated
    source_url        TEXT NOT NULL,
    is_test           BOOLEAN NOT NULL DEFAULT FALSE,
    published_at      TIMESTAMP WITHOUT TIME ZONE,
    last_updated      TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    scraped_at        TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_ftp_status ON ft_funded_projects (status);
CREATE INDEX IF NOT EXISTS ix_ftp_programme ON ft_funded_projects (framework_programme);
CREATE INDEX IF NOT EXISTS ix_ftp_country ON ft_funded_projects (coordinator_country);
CREATE INDEX IF NOT EXISTS ix_ftp_test ON ft_funded_projects (is_test) WHERE is_test = FALSE;

ALTER TABLE ft_funded_projects ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all_ft_projects" ON ft_funded_projects
    FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "authenticated_read_ft_projects" ON ft_funded_projects
    FOR SELECT TO authenticated USING (TRUE);
