-- 266: EMA procurement moves from EMA's page to its Funding & Tenders notices (API audit, "Walk · EMA", 1 Oct 2026)
--
-- The 7 stored rows came from EMA's procurement page: public_url was EMA's home page plus a
-- fragment, document_date held the DEADLINE and no procurement field was filled. Each row moves
-- to the portal notice whose callIdentifier is its EMA reference (exact match, 7 of 7). The
-- deadline moves out of document_date (cleared: the upsert never regresses to NULL, migration 258).
-- Backup: backend/data/backups/economy_items_ema_tender_2026-10-01_before_ema_walk.json

UPDATE public.economy_items SET public_url = 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/tender-details/967da5d1-6957-4aa6-95b1-8cb2b7fc1874-CN', tender_reference = '967da5d1-6957-4aa6-95b1-8cb2b7fc1874-CN',
       guid = '967da5d1-6957-4aa6-95b1-8cb2b7fc1874-CN', source_kind = 'ema_ft_notice', deadline = COALESCE(deadline, document_date), document_date = NULL
 WHERE id = 483301 AND body_code = 'ema' AND item_type = 'tender';
UPDATE public.economy_items SET public_url = 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/tender-details/d1f55919-c8de-462c-b696-b15e069fbc72-CN', tender_reference = 'd1f55919-c8de-462c-b696-b15e069fbc72-CN',
       guid = 'd1f55919-c8de-462c-b696-b15e069fbc72-CN', source_kind = 'ema_ft_notice', deadline = COALESCE(deadline, document_date), document_date = NULL
 WHERE id = 483302 AND body_code = 'ema' AND item_type = 'tender';
UPDATE public.economy_items SET public_url = 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/tender-details/5f5a6b47-db5d-4649-bc0f-1dadb4e7da63-CN', tender_reference = '5f5a6b47-db5d-4649-bc0f-1dadb4e7da63-CN',
       guid = '5f5a6b47-db5d-4649-bc0f-1dadb4e7da63-CN', source_kind = 'ema_ft_notice', deadline = COALESCE(deadline, document_date), document_date = NULL
 WHERE id = 505075 AND body_code = 'ema' AND item_type = 'tender';
UPDATE public.economy_items SET public_url = 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/tender-details/806427cd-58a9-424f-b65e-64ed89895250-CN', tender_reference = '806427cd-58a9-424f-b65e-64ed89895250-CN',
       guid = '806427cd-58a9-424f-b65e-64ed89895250-CN', source_kind = 'ema_ft_notice', deadline = COALESCE(deadline, document_date), document_date = NULL
 WHERE id = 505076 AND body_code = 'ema' AND item_type = 'tender';
UPDATE public.economy_items SET public_url = 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/tender-details/35671487-e3b2-483f-b4f3-78ab87177860-CN', tender_reference = '35671487-e3b2-483f-b4f3-78ab87177860-CN',
       guid = '35671487-e3b2-483f-b4f3-78ab87177860-CN', source_kind = 'ema_ft_notice', deadline = COALESCE(deadline, document_date), document_date = NULL
 WHERE id = 1316261 AND body_code = 'ema' AND item_type = 'tender';
UPDATE public.economy_items SET public_url = 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/tender-details/6c9710ad-aeba-4e4e-813d-9db26333689c-PIN', tender_reference = '6c9710ad-aeba-4e4e-813d-9db26333689c-PIN',
       guid = '6c9710ad-aeba-4e4e-813d-9db26333689c-PIN', source_kind = 'ema_ft_notice', deadline = COALESCE(deadline, document_date), document_date = NULL
 WHERE id = 2933511 AND body_code = 'ema' AND item_type = 'tender';
UPDATE public.economy_items SET public_url = 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/tender-details/35671487-e3b2-483f-b4f3-78ab87177860-PIN', tender_reference = '35671487-e3b2-483f-b4f3-78ab87177860-PIN',
       guid = '35671487-e3b2-483f-b4f3-78ab87177860-PIN', source_kind = 'ema_ft_notice', deadline = COALESCE(deadline, document_date), document_date = NULL
 WHERE id = 2933512 AND body_code = 'ema' AND item_type = 'tender';
