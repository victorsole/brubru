-- 308: an index for the economy lists' default order (20 Oct 2026).
--
-- Every economy list (332 factory endpoints, /funding/all) sorts by
-- coalesce(document_date, creation_date) DESC NULLS LAST, id DESC, and no index matched that
-- expression: /api/v2/funding/eu-funding-recipients (188,187 rows of one body and type) read and
-- sorted every row for each page and answered in 91 s. With this index a page is the first rows
-- of an index range.
--
-- CONCURRENTLY, so the syncs keep writing while it builds (631,837 rows): it cannot run inside a
-- transaction. Apply with autocommit (psql, or a driver connection with autocommit on), NOT with
-- scripts/apply_migration.py, which wraps a file in one transaction.

CREATE INDEX CONCURRENTLY IF NOT EXISTS economy_items_body_type_sortdate
    ON economy_items (body_code, item_type, (coalesce(document_date, creation_date)) DESC NULLS LAST, id DESC);
