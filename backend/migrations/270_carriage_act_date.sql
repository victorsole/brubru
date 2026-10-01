-- 270: the adoption date of the act a carriage points at.
--
-- /api/v2/legislative/oeil/procedures derives document_date from the most recent
-- OEIL key event. That works for a procedure in negotiation and gives nothing for
-- the 1,090 EURLEX carriages, which are adopted acts with no OEIL timeline: a full
-- walk showed document_date empty on 1,545 of 3,382 rows.
--
-- The act's own date is READ from eu_laws (which takes it from Cellar) and stored
-- here, so the endpoint can fall back to it. It is not derived from the CELEX year
-- or from when we imported the row: a date inferred that way would be served as fact
-- and filtered on.
ALTER TABLE legislative_carriages
    ADD COLUMN IF NOT EXISTS act_date date;

COMMENT ON COLUMN legislative_carriages.act_date IS
    'Adoption date of the act this carriage points at, read from eu_laws/Cellar. Fallback for document_date when the row has no OEIL key events.';
