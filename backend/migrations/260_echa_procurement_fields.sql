-- 260: ECHA procurement rows on the procurement fields (columns from migration 256)
--
-- API audit, 30 Sep 2026 ("Walk · ECHA"). The 4 stored ECHA rows hold the reference in
-- guid, the DEADLINE in document_date, and the listing page (#reference) as public_url.
--
-- * Identity is the procedure's own page (Victor, 30 Sep): each row moves to its page,
--   read from ECHA's listing that day, so the next sync updates it in place.
-- * The unique reference rule (migration 256) stays: a market consultation is published
--   under the reference of the procedure it prepares, so it never carries
--   tender_reference (ECHA/2026/OP/0012 here); the body names the procedure.
-- * deadline takes the old document_date, and document_date is CLEARED: the new reader
--   sets it only from a Funding & Tenders notice, and the upsert never regresses a value
--   to NULL, so a left-over deadline would survive as the "publication" date (the ECDC
--   lesson, migration 258).
UPDATE public.economy_items
   SET deadline = COALESCE(deadline, document_date),
       document_date = NULL,
       tender_reference = CASE WHEN id = 5636013 THEN NULL ELSE guid END,
       public_url = CASE id
         WHEN 1046281 THEN 'https://echa.europa.eu/-/nanomaterial-risk-assessment-refining-and-validating-acceptable-variation-in-nanoform-characterisers'
         WHEN 5636013 THEN 'https://echa.europa.eu/-/market-consultation-software-development-services'
         WHEN 485122  THEN 'https://echa.europa.eu/-/call-for-expression-of-interest-for-the-establishment-of-a-database-of-external-remunerated-experts-to-support-public-health-risk-assessments'
         WHEN 485121  THEN 'https://echa.europa.eu/-/dynamic-purchasing-system-dps-for-the-provision-of-it-services-to-echa'
       END
 WHERE body_code = 'echa' AND item_type IN ('tender', 'eoi_call')
   AND id IN (1046281, 5636013, 485122, 485121);
