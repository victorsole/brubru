-- 250: an RSB opinion whose date we have not read must say so, not invent one.
--
-- rsb_opinions.opinion_date was NOT NULL, and the ingest satisfied that by taking the
-- YEAR out of the PDF filename and storing 1 January of it, falling back to 1970-01-01
-- when even the year was missing. All 44 stored rows carried a fabricated day and
-- month; 8 carried the epoch. /commission/rsb-opinions serves that column as the
-- item's date, so a partner filtering or sorting by it was reading invented data, and
-- "newest opinion: 1 January 2020" was what made the endpoint look stalled.
--
-- The ingest now reads datePublished from the publication page's JSON-LD. The column
-- becomes nullable so unknown can stay unknown, and the fabricated values are cleared
-- rather than left to look like real ones. The next ingest run fills in the real dates.

ALTER TABLE rsb_opinions ALTER COLUMN opinion_date DROP NOT NULL;

-- 1 January is the signature of the old filename-year derivation, and 1970-01-01 of
-- the sentinel. Both are cleared; a genuine 1 January opinion will be restored by the
-- next run from the source, which is the only place a real date comes from.
UPDATE rsb_opinions
   SET opinion_date = NULL
 WHERE opinion_date = DATE '1970-01-01'
    OR (EXTRACT(MONTH FROM opinion_date) = 1 AND EXTRACT(DAY FROM opinion_date) = 1);
