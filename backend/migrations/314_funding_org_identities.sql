-- 314: funding_org_identities, one PIC for each VAT number the CORDIS consortia show (26 Oct 2026).
--
-- /funding/partners groups the funded projects' consortia (keyed by the organisation's PIC, CORDIS
-- organisationID) and the Financial Transparency System's beneficiaries (no PIC; a VAT number on
-- 162,742 of 187,961 rows). An FTS beneficiary whose VAT number a CORDIS organisation also carries
-- is that organisation: this table holds the pairing, rebuilt from the consortia every week by
-- scripts/refresh_org_identities.py. A VAT number seen with two PICs is ambiguous and left out (the
-- beneficiary then stands under its VAT number); a name alone never joins two records.

CREATE TABLE IF NOT EXISTS public.funding_org_identities (
    vat_key      TEXT        PRIMARY KEY,               -- upper case, letters and digits only
    pic          TEXT        NOT NULL,
    name         TEXT,                                  -- the name the consortia give it most often
    country      TEXT,                                  -- its EU-style country code
    projects     INTEGER     NOT NULL DEFAULT 0,        -- consortium memberships seen
    first_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated TIMESTAMPTZ NOT NULL DEFAULT now(),
    scraped_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_funding_org_identities_pic ON public.funding_org_identities (pic);

ALTER TABLE public.funding_org_identities ENABLE ROW LEVEL SECURITY;
CREATE POLICY funding_org_identities_public_read ON public.funding_org_identities
    FOR SELECT TO anon, authenticated USING (true);
REVOKE ALL ON public.funding_org_identities FROM anon, authenticated;
GRANT SELECT ON public.funding_org_identities TO anon, authenticated;
GRANT ALL ON public.funding_org_identities TO service_role;

CREATE TRIGGER trg_funding_org_identities_touch BEFORE UPDATE ON public.funding_org_identities
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen');
