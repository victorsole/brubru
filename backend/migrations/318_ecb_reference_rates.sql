-- 318: ecb_reference_rates, the ECB's euro foreign exchange reference rates (29 Oct 2026, funding
-- standard Phase 2 step 6: `amount_eur` at the ECB reference rate of the item's own date).
--
-- Read daily by scripts/sync_ecb_reference_rates.py (services/funding/ecb_rates.py) from the ECB
-- Data Portal, series EXR.D.<currency>.EUR.SP00.A: one row per currency and day the ECB published a
-- reference rate (TARGET working days, about 14:15 CET), from 1 Jan 2020. Reference rates only: the
-- four indicative series (ARS, DZD, MAD, TWD, discontinued 30 Oct 2020) are not read. `rate` is
-- units of the currency for one euro, as the ECB states it. Not served by any endpoint: the funding
-- lists convert an amount with it (services/funding/shared_fields.amount_eur_sql).
CREATE TABLE IF NOT EXISTS public.ecb_reference_rates (
    currency      TEXT        NOT NULL,                -- ISO 4217 code (USD, PLN ...)
    rate_date     DATE        NOT NULL,                -- the day the ECB published the rate
    rate          NUMERIC     NOT NULL CHECK (rate > 0), -- units of the currency for 1 EUR
    series_key    TEXT        NOT NULL,                -- EXR.D.USD.EUR.SP00.A
    source_url    TEXT        NOT NULL,                -- the series on data.ecb.europa.eu
    first_seen    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated  TIMESTAMPTZ NOT NULL DEFAULT now(),
    scraped_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (currency, rate_date)
);

ALTER TABLE public.ecb_reference_rates ENABLE ROW LEVEL SECURITY;
CREATE POLICY ecb_reference_rates_public_read ON public.ecb_reference_rates
    FOR SELECT TO anon, authenticated USING (true);
REVOKE ALL ON public.ecb_reference_rates FROM anon, authenticated;
GRANT SELECT ON public.ecb_reference_rates TO anon, authenticated;
GRANT ALL ON public.ecb_reference_rates TO service_role;

CREATE TRIGGER trg_ecb_reference_rates_touch BEFORE UPDATE ON public.ecb_reference_rates
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen');
