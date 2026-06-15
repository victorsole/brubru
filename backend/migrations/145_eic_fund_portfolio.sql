-- 145_eic_fund_portfolio.sql
-- Move 3 of #5 EIC implementation (15 Jun 2026).
--
-- Holds the EIC Fund's public investee portfolio scraped from
-- https://eic.ec.europa.eu/eic-fund/eic-fund-companies-portfolio_en (paginated +
-- filterable by 12 sector themes). Used by the Tenderator drawer's
-- "Past grantees on similar calls" panel to give EIC Accelerator / STEP
-- applicants concrete social-proof examples (who got the equity, in which
-- sector, in which country).
--
-- Companies are unique by name; a single company can belong to multiple
-- themes but we capture only the FIRST seen theme to keep the row 1-to-1.
-- If multi-theme attribution becomes important, add a join table later.

CREATE TABLE IF NOT EXISTS public.eic_fund_portfolio_companies (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    country     TEXT,                 -- ISO-2 country code (e.g. 'FR', 'DE')
    country_name TEXT,                -- "France", "Germany" — captured from page
    theme_code  INTEGER,              -- Drupal taxonomy id (41, 48, 95-104)
    theme_name  TEXT,                 -- "Advanced Manufacturing & Materials" etc.
    description TEXT,
    source_url  TEXT NOT NULL,        -- the EC page where the company was scraped
    scraped_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT eic_fund_portfolio_companies_name_uniq UNIQUE (name)
);

CREATE INDEX IF NOT EXISTS idx_eic_fund_portfolio_theme_code
    ON public.eic_fund_portfolio_companies (theme_code);
CREATE INDEX IF NOT EXISTS idx_eic_fund_portfolio_country
    ON public.eic_fund_portfolio_companies (country);
-- Trigram fuzzy-match index (optional — only if pg_trgm is enabled). The
-- Drupal portfolio names are short and stable, so plain B-tree on name lookups
-- via the UNIQUE constraint is enough for normal access; the trigram index is
-- only useful for "find investee similar to <call title>" matching. Skipped
-- here to keep the migration independent of pg_trgm availability.

-- RLS: portfolio is public reference data — anon + authenticated SELECT,
-- service_role full access. Mirrors the established pattern in migrations
-- 041/042/064/065/069 (Supabase Data API grants — set 15 May 2026).
ALTER TABLE public.eic_fund_portfolio_companies ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "eic_fund_portfolio_public_read" ON public.eic_fund_portfolio_companies;
CREATE POLICY "eic_fund_portfolio_public_read"
    ON public.eic_fund_portfolio_companies
    FOR SELECT
    TO anon, authenticated
    USING (true);

DROP POLICY IF EXISTS "eic_fund_portfolio_service_all" ON public.eic_fund_portfolio_companies;
CREATE POLICY "eic_fund_portfolio_service_all"
    ON public.eic_fund_portfolio_companies
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

GRANT SELECT ON public.eic_fund_portfolio_companies TO anon, authenticated;
GRANT ALL    ON public.eic_fund_portfolio_companies TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.eic_fund_portfolio_companies_id_seq TO service_role;

COMMENT ON TABLE public.eic_fund_portfolio_companies IS
    'EIC Fund publicly disclosed investees, scraped from eic.ec.europa.eu. Used by Tenderator drawer for EIC past-grantees social proof.';
