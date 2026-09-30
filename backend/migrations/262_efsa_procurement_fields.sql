-- 262: EFSA procurement rows on the procurement fields (columns from migration 256)
--
-- API audit, 30 Sep 2026 ("Walk · EFSA"). The 10 stored EFSA rows each point at their
-- Funding & Tenders notice; their document_date is the DEADLINE. tender_reference = the
-- notice id (the last segment of the address); deadline takes the old document_date, and
-- document_date is CLEARED (the ECDC lesson, migration 258): the next sync writes the
-- notice's publication date. The new reader produces the same addresses, so these rows
-- are updated in place.
UPDATE public.economy_items
   SET tender_reference = regexp_replace(public_url, '^.*/tender-details/', ''),
       deadline = COALESCE(deadline, document_date),
       document_date = NULL
 WHERE body_code = 'efsa' AND item_type = 'tender'
   AND public_url LIKE '%/tender-details/%' AND tender_reference IS NULL;
