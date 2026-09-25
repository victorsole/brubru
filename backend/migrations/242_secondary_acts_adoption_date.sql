-- Delegated and implementing acts carried no act dates at all (GovClipping, 25 Sep 2026).
--
-- /legislative/delegated-acts and /legislative/implementing-acts served creation_date and
-- last_updated only, and both of those hold OUR import timestamps, so a regulation from
-- 2014 looked as though it were published in 2026. Measured: 4 of 7,521 rows had a
-- publication_date, while 6,976 carried a CELEX that Cellar can date.
--
-- Worse than cosmetic: the list endpoint SORTS and FILTERS on publication_date, so
-- published_from / published_to answered from the 4 rows that had one and returned almost
-- nothing, with a 200 and no indication that the filter had nothing to work with.
--
-- Cellar distinguishes the two dates an act has, and so do we now:
--   publication_date <- cdm:work_date_creation_legacy   the Official Journal date
--   adoption_date    <- cdm:work_date_document          the date the Commission adopted it
-- For Delegated Regulation (EU) 2016/161 that is 9 February 2016 (OJ L 32) and
-- 2 October 2015 respectively.
--
-- `publication_date` keeps its name and meaning, so the `document_date` datapoint that
-- aliases it keeps its contract; `adoption_date` is added alongside rather than
-- redefining a field clients already read.
ALTER TABLE secondary_acts ADD COLUMN IF NOT EXISTS adoption_date DATE;

COMMENT ON COLUMN secondary_acts.adoption_date IS
    'Date the act was adopted (Cellar cdm:work_date_document). Distinct from '
    'publication_date, which is the Official Journal date (cdm:work_date_creation_legacy).';

CREATE INDEX IF NOT EXISTS ix_secondary_acts_publication_date
    ON secondary_acts (publication_date DESC NULLS LAST);
