-- 313: fts_commitments, the EU Financial Transparency System file's own columns (26 Oct 2026).
--
-- /funding/eu-funding-recipients served the FTS rows as text lines only (beneficiary, amount,
-- programme... inside body_txt): no field, no filter, and /international-cooperation parsed its
-- fields back out of that text. The file states much more than we kept: whether the beneficiary
-- coordinates, its registration and VAT numbers, city, NUTS2, ITS OWN contracted amount (the text
-- carried the whole commitment's total, shared by every beneficiary of it), the call and project
-- IDs (the join to funded projects), beneficiary type, project end, benefiting country. One row
-- per economy_items row (the same FTS record, same id), re-read from the file by
-- scripts/sync_fts_commitments.py, never parsed from our own text. Address and postal code are
-- not kept (not needed to find a partner). Trio first_seen / last_updated / scraped_at as 288.

CREATE TABLE IF NOT EXISTS public.fts_commitments (
    economy_item_id                    BIGINT      PRIMARY KEY REFERENCES public.economy_items(id) ON DELETE CASCADE,
    year                               INTEGER     NOT NULL,   -- the FTS file's year
    budget                             TEXT,                   -- EU budget | Other European Bodies | ...
    lc_reference                       TEXT,                   -- Reference of the Legal Commitment
    budget_reference                   TEXT,                   -- Reference (Budget)
    beneficiary                        TEXT        NOT NULL,
    registration_number                TEXT,                   -- main registration number of the beneficiary
    vat_number                         TEXT,                   -- as the file writes it
    vat_key                            TEXT,                   -- the same, upper case, letters and digits only (the join key)
    is_nfpo                            BOOLEAN,                -- not-for-profit organisation
    is_ngo                             BOOLEAN,
    is_coordinator                     BOOLEAN,
    city                               TEXT,
    country                            TEXT,                   -- beneficiary country, as the file names it
    country_code                       TEXT,                   -- its EU-style code (EL, UK, else ISO 3166 alpha-2), from config/country_codes.json
    nuts2                              TEXT,
    beneficiary_amount_eur             NUMERIC,                -- the beneficiary's contracted amount
    beneficiary_estimated_amount_eur   NUMERIC,
    beneficiary_estimated_consumed_eur NUMERIC,
    commitment_contracted_eur          NUMERIC,                -- (A)
    commitment_adjustment_eur          NUMERIC,                -- (B)
    commitment_total_eur               NUMERIC,                -- (A+B), shared by the commitment's beneficiaries
    commitment_consumed_eur            NUMERIC,
    amount_source                      TEXT,                   -- how the file split the amount
    expense_type                       TEXT,
    call_id                            TEXT,
    project_id                         TEXT,                   -- grant agreement number (join to ft_funded_projects)
    project_acronym                    TEXT,
    subject                            TEXT,
    dg                                 TEXT,                   -- responsible department
    budget_line_number                 TEXT,
    budget_line_name                   TEXT,
    programme                          TEXT,
    beneficiary_type                   TEXT,
    project_start                      DATE,
    project_end                        DATE,
    funding_type                       TEXT,                   -- "Type of contract" (Action Grant, the procurement categories...)
    management_type                    TEXT,
    benefiting_country                 TEXT,
    first_seen                         TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated                       TIMESTAMPTZ NOT NULL DEFAULT now(),
    scraped_at                         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fts_commitments_dg ON public.fts_commitments (dg);
CREATE INDEX IF NOT EXISTS idx_fts_commitments_country ON public.fts_commitments (country);
CREATE INDEX IF NOT EXISTS idx_fts_commitments_programme ON public.fts_commitments (programme);
CREATE INDEX IF NOT EXISTS idx_fts_commitments_funding_type ON public.fts_commitments (funding_type);
CREATE INDEX IF NOT EXISTS idx_fts_commitments_year ON public.fts_commitments (year);
CREATE INDEX IF NOT EXISTS idx_fts_commitments_project ON public.fts_commitments (project_id) WHERE project_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fts_commitments_vat ON public.fts_commitments (vat_key) WHERE vat_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fts_commitments_country_code ON public.fts_commitments (country_code);
CREATE INDEX IF NOT EXISTS idx_fts_commitments_amount ON public.fts_commitments (beneficiary_amount_eur);
-- /funding/partners matches an organisation by what it was paid for, not by its name.
CREATE INDEX IF NOT EXISTS idx_fts_commitments_subject_tsv ON public.fts_commitments
    USING gin (to_tsvector('english', coalesce(subject, '')));

ALTER TABLE public.fts_commitments ENABLE ROW LEVEL SECURITY;
CREATE POLICY fts_commitments_public_read ON public.fts_commitments
    FOR SELECT TO anon, authenticated USING (true);
REVOKE ALL ON public.fts_commitments FROM anon, authenticated;
GRANT SELECT ON public.fts_commitments TO anon, authenticated;
GRANT ALL ON public.fts_commitments TO service_role;

-- last_updated moves only when a stated value changes; a weekly re-read of the same file does not.
CREATE TRIGGER trg_fts_commitments_touch BEFORE UPDATE ON public.fts_commitments
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen');
