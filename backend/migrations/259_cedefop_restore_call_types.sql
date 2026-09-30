-- 259: undo the first daily run's reclassification of 9 archived Cedefop calls
--
-- 30 Sep 2026, 10:12 UTC: the new Cedefop reader ran in daily mode (detail pages only for
-- listing pages 0-1 and live procedures). For the archive it fell back to guessing tender
-- vs call for expression of interest from the reference, and for 9 old calls the guess
-- disagreed with the page's own Procurement type (read by the full backfill that morning):
--   7 calls with no reference were written a SECOND time under item_type 'tender';
--   2 calls with a reference (EACEA/07, EACEA/17/08) were moved to 'tender' by the
--     re-point-by-reference step.
-- The writer now keeps the stored type for any row whose page was not re-read
-- (sync_economy._keep_stored_type). Backup: backend/data/backups/economy_items_cedefop_types_2026_09_30.csv
DELETE FROM public.economy_items
 WHERE body_code = 'cedefop' AND item_type = 'tender'
   AND id IN (5767890, 5767922, 5767977, 5767978, 5768012, 5768013, 5768014)
   AND tender_reference IS NULL;
UPDATE public.economy_items SET item_type = 'eoi_call'
 WHERE body_code = 'cedefop' AND item_type = 'tender'
   AND id IN (5767054, 5767059) AND tender_reference IN ('EACEA/07', 'EACEA/17/08');
