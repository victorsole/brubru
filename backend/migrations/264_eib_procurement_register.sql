-- 264: EIB procurement moves from TED notices to EIB's own register (API audit, "Walk · EIB", 1 Oct 2026)
--
-- The 21 stored rows were TED notices: document_date held the DEADLINE, no procurement field
-- was filled, and one procedure was split across its notices (CFT-1747 x4, CFT-1844 x3).
-- Each row was matched to the EIB procedure whose register page lists its TED notice:
-- * 9 rows move to their procedure's page (one per procedure), with EIB's reference as
--   published (two technical-assistance pages publish the TED number: 426186, 499035).
-- * 3 rows are procedures absent from EIB's register (CFT-1846, CFT-1847, CFT-1856): they
--   stay at their TED address and the TED supplement updates them in place.
-- * 9 rows go: 5 extra notices of a procedure now held once; 2 notices of register
--   procedures (MAA-010008, 426186) whose pages omit them; 2 joint procedures led by
--   another body (EC-COMM/2026/OP/0019, CURIA/2026/OP/0001).
-- document_date is cleared on every remaining row (it was the deadline) and kept as deadline:
-- the upsert never regresses a value to NULL, so a left-over deadline would survive (migration 258).
-- Backup: backend/data/backups/economy_items_eib_tender_2026-10-01_before_eib_walk.json

DELETE FROM public.economy_items WHERE body_code = 'eib' AND item_type = 'tender'
   AND id IN (485124, 485125, 497161, 840932, 485128, 762274, 3052073, 840933, 1536246);

UPDATE public.economy_items
   SET deadline = COALESCE(deadline, document_date), document_date = NULL
 WHERE body_code = 'eib' AND item_type = 'tender' AND source_kind = 'eib_procurement'
   AND id IN (485123, 485126, 485127, 497158, 497159, 497162, 840931, 1106501, 1841056, 497160, 5147831, 5809111);

UPDATE public.economy_items SET public_url = 'https://www.eib.org/en/about/procurement/calls/all/cft-1747', tender_reference = 'CFT-1747', guid = 'CFT-1747'
 WHERE id = 485123 AND body_code = 'eib' AND item_type = 'tender';
UPDATE public.economy_items SET public_url = 'https://www.eib.org/en/about/procurement/calls/all/cft-1816', tender_reference = 'CFT-1816', guid = 'CFT-1816'
 WHERE id = 485126 AND body_code = 'eib' AND item_type = 'tender';
UPDATE public.economy_items SET public_url = 'https://www.eib.org/en/about/procurement/calls-technical-assistance/all/maa-010008', tender_reference = 'MAA-010008', guid = 'MAA-010008'
 WHERE id = 485127 AND body_code = 'eib' AND item_type = 'tender';
UPDATE public.economy_items SET public_url = 'https://www.eib.org/en/about/procurement/calls-technical-assistance/all/aa-012642002', tender_reference = '426186', guid = '426186'
 WHERE id = 497158 AND body_code = 'eib' AND item_type = 'tender';
UPDATE public.economy_items SET public_url = 'https://www.eib.org/en/about/procurement/calls/all/cft-1844', tender_reference = 'CFT-1844', guid = 'CFT-1844'
 WHERE id = 497159 AND body_code = 'eib' AND item_type = 'tender';
UPDATE public.economy_items SET public_url = 'https://www.eib.org/en/about/procurement/calls-technical-assistance/all/aa-012824001', tender_reference = 'AA-012824-001', guid = 'AA-012824-001'
 WHERE id = 497162 AND body_code = 'eib' AND item_type = 'tender';
UPDATE public.economy_items SET public_url = 'https://www.eib.org/en/about/procurement/calls-technical-assistance/all/aa-013468001', tender_reference = '499035', guid = '499035'
 WHERE id = 840931 AND body_code = 'eib' AND item_type = 'tender';
UPDATE public.economy_items SET public_url = 'https://www.eib.org/en/about/procurement/calls-technical-assistance/all/aa-011624003', tender_reference = 'AA-011624-003', guid = 'AA-011624-003'
 WHERE id = 1106501 AND body_code = 'eib' AND item_type = 'tender';
UPDATE public.economy_items SET public_url = 'https://www.eib.org/en/about/procurement/calls-technical-assistance/all/aa-013009001', tender_reference = 'AA-013009-001', guid = 'AA-013009-001'
 WHERE id = 1841056 AND body_code = 'eib' AND item_type = 'tender';

-- the three TED-only rows are written by source_kind eib_ted from now on
UPDATE public.economy_items SET source_kind = 'eib_ted'
 WHERE id IN (497160, 5147831, 5809111) AND body_code = 'eib' AND item_type = 'tender';
