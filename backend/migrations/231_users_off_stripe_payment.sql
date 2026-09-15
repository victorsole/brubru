-- 231: record payment that did NOT go through Stripe.
--
-- WHY
-- ---
-- WAPU (paid subscriber + >=1 core action in 7 days) has required
-- `stripe_subscription_id IS NOT NULL` since 27 Aug 2026, because a tier string is
-- written by provisioning scripts as readily as by Stripe and a demo shell once
-- reported itself as a paying user. That guard is right and stays.
--
-- But on 15 Sep 2026 Victor confirmed two customers who pay by invoice/transfer:
--   * Terraqui (jcastella@terraqui.com): EUR 39 for September 2026, trial month.
--   * GovClipping (team@govclipping.com, Jordi Montoya): EUR 990 a year
--     (EUR 99/month, two months free).
-- Neither has a Stripe subscription, so the north star could never count them.
-- The fix is EVIDENCE of payment in its own columns, set by a human from a real
-- payment, never inferred from the tier.
--
-- WHAT
-- ----
--   off_stripe_paid_until  period end of a verified non-Stripe payment (NULL = none)
--   billing_note           what was paid, how, and who confirmed it
--
-- Nullable, no default, no backfill beyond the two confirmed customers below.
-- Existing RLS on users is unchanged (no new table, so no new GRANT needed).

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS off_stripe_paid_until TIMESTAMPTZ;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS billing_note TEXT;

UPDATE public.users
   SET off_stripe_paid_until = '2026-09-30 23:59:59+00',
       billing_note = 'EUR 39 for September 2026, trial month, paid outside Stripe. Confirmed by Victor 15 Sep 2026.'
 WHERE email = 'jcastella@terraqui.com' AND off_stripe_paid_until IS NULL;

UPDATE public.users
   SET off_stripe_paid_until = '2027-09-04 23:59:59+00',
       billing_note = 'EUR 990 per year (EUR 99/month, two months free), paid outside Stripe. Confirmed by Victor 15 Sep 2026. Period end taken from the MCP key issued 4 Sep 2026 (expires 4 Sep 2027): CONFIRM the actual payment date.'
 WHERE email = 'team@govclipping.com' AND off_stripe_paid_until IS NULL;
