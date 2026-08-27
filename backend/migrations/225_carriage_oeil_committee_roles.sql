-- 223_carriage_oeil_committee_roles.sql
-- D4: give legislative_carriages somewhere to record what OEIL actually says.
--
-- Measured 27 Aug 2026 across all 2,789 carriages:
--     rapporteur_mep_id populated ......      0
--     lead_committee populated .........  1,038
--     opinion_committees non-empty .....      1
--     committees non-empty .............      1
--
-- `lead_committee` was set to `item.committees[0]` -- whichever committee came
-- first in a flat list from the OEIL XML feed, which does not distinguish the
-- committee RESPONSIBLE from a committee FOR OPINION. For 2025/2081(INI) that
-- made IMCO the lead when OEIL says CULT and IMCO only holds an opinion.
--
-- The procedure page carries the distinction, and Brubru already stores that page
-- in oeil_text_body for 892 carriages -- so this is a parse of data we hold, not
-- 2,789 new fetches.
--
-- Forecasts get their own column for the same reason the OEIL page keeps them in
-- their own section: "Key events" is what HAPPENED, "Forecasts" is what is
-- EXPECTED. Merged, an indicative plenary date reads as a committee vote that has
-- already taken place -- which is what Brubru was reporting.

ALTER TABLE public.legislative_carriages
    ADD COLUMN IF NOT EXISTS rapporteur_name       text,
    ADD COLUMN IF NOT EXISTS rapporteur_appointed  date,
    ADD COLUMN IF NOT EXISTS oeil_forecasts        json,
    -- NULL = never parsed. Distinct from an empty parse, so a carriage whose page
    -- we have never read cannot be mistaken for one that genuinely has no
    -- opinion committees.
    ADD COLUMN IF NOT EXISTS oeil_roles_parsed_at  timestamptz;

CREATE INDEX IF NOT EXISTS idx_carriages_rapporteur_name
    ON public.legislative_carriages (rapporteur_name)
    WHERE rapporteur_name IS NOT NULL;

COMMENT ON COLUMN public.legislative_carriages.oeil_forecasts IS
    'OEIL "Forecasts" rows: EXPECTED events. Never merge with oeil_key_events, '
    'which records what has already happened.';
COMMENT ON COLUMN public.legislative_carriages.oeil_roles_parsed_at IS
    'When committee roles were last parsed from oeil_text_body. NULL means never '
    'parsed -- not that the procedure has no opinion committees.';
