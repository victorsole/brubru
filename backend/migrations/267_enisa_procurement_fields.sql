-- 267: ENISA procurement rows on the procurement fields (API audit, "Walk · ENISA", 1 Oct 2026)
--
-- The 15 stored ENISA rows (page 0 of 26) keep their addresses: the new reader writes the
-- same procedure pages. Their document_date held the DEADLINE; it moves to deadline and is
-- cleared, because the upsert never regresses a value to NULL and the new reader sets
-- document_date only from the linked Funding & Tenders notice (migration 258's lesson).
-- Backup: backend/data/backups/economy_items_enisa_procurement_2026-10-01_before_enisa_walk.json
UPDATE public.economy_items
   SET deadline = COALESCE(deadline, document_date), document_date = NULL
 WHERE body_code = 'enisa' AND item_type IN ('tender', 'eoi_call')
   AND source_kind = 'enisa_procurement';
