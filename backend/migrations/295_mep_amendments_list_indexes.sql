-- 295: /api/v2/parliament/amendments pages read through an index (16 Oct 2026).
--
-- The list orders by document_date DESC NULLS LAST, amendment_number, id and the incremental
-- sync filters on updated_at; neither had an index, so every page sorted all 64,198
-- amendments by a parallel seq scan of 127 MB. With the database's disk reads throttled that
-- morning a page took 60-99 s. CONCURRENTLY: no write is blocked while they build.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_mep_amendments_list_order
    ON mep_amendments (document_date DESC NULLS LAST, amendment_number, id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_mep_amendments_updated_at
    ON mep_amendments (updated_at);
