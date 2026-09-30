-- 257: ECDC procurement rows on the procurement fields (columns from migration 256)
--
-- API audit, 30 Sep 2026 ("Walk · ECDC"). The 29 stored ECDC rows hold the reference in
-- guid and the DEADLINE in document_date (the old reader's design). Move both to their
-- own columns; the next sync (ECDC_FULL_DETAILS=1 for the archive) writes tender_reference,
-- status and deadline from the listing and puts the page's article:published_time in
-- document_date. No duplicates to merge: 29 rows, 29 distinct references (checked).
UPDATE public.economy_items
   SET tender_reference = guid,
       deadline = COALESCE(deadline, document_date)
 WHERE body_code = 'ecdc' AND item_type = 'tender'
   AND tender_reference IS NULL AND guid IS NOT NULL AND guid <> '';
