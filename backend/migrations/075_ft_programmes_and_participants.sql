-- migrations/075_ft_programmes_and_participants.sql
-- Phase 5 of the Tenderator dashboard reform (19 May 2026).
--
-- Two small reference tables for the EU Funding & Tenders portal:
--   * ft_programmes    - the high-level funding programmes (Horizon Europe,
--                        LIFE, CEF, etc.) that contain the calls.
--   * ft_participants  - PIC-keyed organisation profiles from the F&T
--                        Participant Register.
--
-- Both ship is_test BOOLEAN DEFAULT FALSE so future fixtures never leak
-- into production queries (per feedback_seed_fixtures_contaminate_prod).
--
-- Per CLAUDE.md hard rule (Supabase Data API grants mandatory, set 15 May
-- 2026): every new public.* table needs RLS + GRANTs to anon, authenticated,
-- and service_role.

BEGIN;

-- ====================================================================
-- ft_programmes
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.ft_programmes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    programme_code  VARCHAR(40) NOT NULL UNIQUE,    -- HE, LIFE, CEF, DEP, EU4H, ERASMUS, CREA, EIC, JTM, AMIF, ISF, BMVI, ...
    name            TEXT NOT NULL,
    parent_framework TEXT,                          -- MFF 2021-2027 / MFF 2014-2020
    budget_total    NUMERIC(20, 2),
    budget_currency CHAR(3) DEFAULT 'EUR',
    period_start    DATE,
    period_end      DATE,
    description     TEXT,
    objectives      TEXT,
    source_url      TEXT NOT NULL,
    is_test         BOOLEAN NOT NULL DEFAULT FALSE,
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ft_programmes_code ON public.ft_programmes(programme_code);
CREATE INDEX IF NOT EXISTS idx_ft_programmes_test ON public.ft_programmes(is_test);

ALTER TABLE public.ft_programmes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ft_programmes_public_read ON public.ft_programmes;
CREATE POLICY ft_programmes_public_read ON public.ft_programmes
    FOR SELECT
    TO anon, authenticated
    USING (is_test = FALSE);

DROP POLICY IF EXISTS ft_programmes_service_all ON public.ft_programmes;
CREATE POLICY ft_programmes_service_all ON public.ft_programmes
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

GRANT SELECT ON public.ft_programmes TO anon, authenticated;
GRANT ALL    ON public.ft_programmes TO service_role;

-- ====================================================================
-- ft_participants
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.ft_participants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pic             VARCHAR(20) NOT NULL UNIQUE,    -- Participant Identification Code, e.g. "999999999"
    legal_name      TEXT NOT NULL,
    short_name      TEXT,
    country         CHAR(2),                         -- ISO 3166-1 alpha-2
    org_type        VARCHAR(8),                      -- HE | REC | PUB | OTH | SME
    vat             VARCHAR(30),
    address         TEXT,
    website         TEXT,
    project_count   INTEGER NOT NULL DEFAULT 0,
    source_url      TEXT NOT NULL,
    is_test         BOOLEAN NOT NULL DEFAULT FALSE,
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ft_participants_pic     ON public.ft_participants(pic);
CREATE INDEX IF NOT EXISTS idx_ft_participants_country ON public.ft_participants(country);
CREATE INDEX IF NOT EXISTS idx_ft_participants_test    ON public.ft_participants(is_test);

ALTER TABLE public.ft_participants ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ft_participants_public_read ON public.ft_participants;
CREATE POLICY ft_participants_public_read ON public.ft_participants
    FOR SELECT
    TO anon, authenticated
    USING (is_test = FALSE);

DROP POLICY IF EXISTS ft_participants_service_all ON public.ft_participants;
CREATE POLICY ft_participants_service_all ON public.ft_participants
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

GRANT SELECT ON public.ft_participants TO anon, authenticated;
GRANT ALL    ON public.ft_participants TO service_role;

-- ====================================================================
-- Seed: the dozen well-known programmes. Real budgets, real period
-- dates, real F&T portal URLs. Idempotent via ON CONFLICT DO NOTHING.
-- ====================================================================
INSERT INTO public.ft_programmes (programme_code, name, parent_framework, budget_total, budget_currency, period_start, period_end, description, source_url) VALUES
    ('HE',       'Horizon Europe',
                 'MFF 2021-2027',          95500000000, 'EUR', '2021-01-01', '2027-12-31',
                 'Research and innovation framework programme. Three pillars: Excellent Science, Global Challenges & European Industrial Competitiveness, Innovative Europe.',
                 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/programmes/horizon'),
    ('DEP',      'Digital Europe Programme',
                 'MFF 2021-2027',           7600000000, 'EUR', '2021-01-01', '2027-12-31',
                 'Funding programme focused on the digital transformation of Europe: HPC, AI, cybersecurity, advanced digital skills, deployment.',
                 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/programmes/digital'),
    ('LIFE',     'LIFE Programme',
                 'MFF 2021-2027',           5430000000, 'EUR', '2021-01-01', '2027-12-31',
                 'EU funding instrument for environment and climate action.',
                 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/programmes/life'),
    ('CEF',      'Connecting Europe Facility',
                 'MFF 2021-2027',          33710000000, 'EUR', '2021-01-01', '2027-12-31',
                 'Investment in infrastructure across transport, energy, and digital networks.',
                 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/programmes/cef'),
    ('EU4H',     'EU4Health',
                 'MFF 2021-2027',           5300000000, 'EUR', '2021-01-01', '2027-12-31',
                 'Largest-ever EU health programme. Crisis preparedness, cancer plan, digital health, pharmaceuticals.',
                 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/programmes/eu4h'),
    ('ERASMUS',  'Erasmus+',
                 'MFF 2021-2027',          26200000000, 'EUR', '2021-01-01', '2027-12-31',
                 'EU programme for education, training, youth, and sport.',
                 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/programmes/erasmus2027'),
    ('CREA',     'Creative Europe',
                 'MFF 2021-2027',           2440000000, 'EUR', '2021-01-01', '2027-12-31',
                 'Programme for the cultural and creative sectors. Three strands: CULTURE, MEDIA, CROSS-SECTORAL.',
                 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/programmes/crea2027'),
    ('EIC',      'European Innovation Council',
                 'Horizon Europe pillar',  10100000000, 'EUR', '2021-01-01', '2027-12-31',
                 'EIC Pathfinder, EIC Transition, EIC Accelerator. Equity-and-grant blended finance for deep-tech startups and scale-ups.',
                 'https://eic.ec.europa.eu/'),
    ('JTM',      'Just Transition Mechanism',
                 'MFF 2021-2027',          55000000000, 'EUR', '2021-01-01', '2027-12-31',
                 'Targeted support to help regions most affected by the green transition.',
                 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/programmes/just-transition'),
    ('AMIF',     'Asylum, Migration and Integration Fund',
                 'MFF 2021-2027',           9882000000, 'EUR', '2021-01-01', '2027-12-31',
                 'EU funding for asylum, migration, and integration policy.',
                 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/programmes/amif2027'),
    ('ISF',      'Internal Security Fund',
                 'MFF 2021-2027',           1931000000, 'EUR', '2021-01-01', '2027-12-31',
                 'Police cooperation, organised crime, terrorism, crisis management.',
                 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/programmes/isf2027'),
    ('BMVI',     'Border Management and Visa Instrument',
                 'MFF 2021-2027',           6240000000, 'EUR', '2021-01-01', '2027-12-31',
                 'Strengthen the EUs external borders and common visa policy.',
                 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/programmes/bmvi2027'),
    ('H2020',    'Horizon 2020',
                 'MFF 2014-2020',          77000000000, 'EUR', '2014-01-01', '2020-12-31',
                 'Predecessor to Horizon Europe. Closed for new calls, but 81k+ funded projects in the CORDIS database.',
                 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/programmes/h2020'),
    ('FP7',      'FP7',
                 'MFF 2007-2013',          50500000000, 'EUR', '2007-01-01', '2013-12-31',
                 'Seventh Framework Programme. Predecessor to Horizon 2020.',
                 'https://cordis.europa.eu/programme/rcn/fp7/en')
ON CONFLICT (programme_code) DO NOTHING;

COMMIT;
