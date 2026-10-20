-- 305: the buyer's legal type and level of government on TED notices (20 Oct 2026).
--
-- A partner asked whether a buyer is municipal, regional, national or EU, and only the name was
-- served. Every stored eForms XML carries the buyer's legal type (BT-11, code list
-- buyer-legal-type: la, ra, cga, eu-ins-bod-ag, body-pl-la ...) and nothing read it.
-- buyer_level is derived from it (services/tenders/eforms_parser.BUYER_LEVELS) and stays NULL
-- where the code does not name a level (a plain body governed by public law, a public
-- undertaking, a defence contractor). Filled for the stock by
-- scripts/backfill_tender_notice_fields.py; new notices by fetch_tenders.py.
--
-- Additive, nullable, no default: no row is rewritten and the touch trigger does not fire.
-- tenders is an existing public table, so its grants already cover the new columns.

SET LOCAL lock_timeout = '10s';

ALTER TABLE public.tenders
    ADD COLUMN IF NOT EXISTS buyer_legal_type varchar(40),
    ADD COLUMN IF NOT EXISTS buyer_level varchar(20);

CREATE INDEX IF NOT EXISTS ix_tenders_buyer_level ON public.tenders (buyer_level);
