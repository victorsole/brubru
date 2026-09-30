-- 260: ECHA procurement rows on the procurement fields (columns from migration 256)
--
-- API audit, 30 Sep 2026 ("Walk · ECHA"). The 4 stored ECHA rows hold the reference in
-- guid and the DEADLINE in document_date. Move the deadline to its own column AND clear
-- document_date: the new reader sets it only from a Funding & Tenders notice's publication
-- date, and the upsert never regresses a value to NULL, so a left-over deadline would
-- survive as the "publication" date (the ECDC lesson, migration 258).
-- public_url moves from the listing page (#reference) to each procedure's own page on the
-- next sync, through the re-point-by-reference step (all 4 rows have a reference).
UPDATE public.economy_items
   SET tender_reference = guid,
       deadline = COALESCE(deadline, document_date),
       document_date = NULL
 WHERE body_code = 'echa' AND item_type IN ('tender', 'eoi_call')
   AND tender_reference IS NULL AND guid IS NOT NULL AND guid <> '';
