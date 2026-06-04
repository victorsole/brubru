-- 094: Repair garbage committee_work_items titles from the linked carriage.
--
-- The committee "Work in Progress" scraper frequently captured page chrome
-- instead of the real title, e.g.
--   "***I Ordinary legislative procedure (COD) first reading AGRI ENVI"
--   "Delegated acts (DEA) ENVI"
--   "Procedure File: 2025/2880(RSP)"
-- 152 of these rows are linked to a legislative_carriages row (via
-- legislative_carriage_id) that already holds a clean title. Borrow it.
-- The remaining rows are handled in the frontend (hidden as technical /
-- graceful fallback title) and can be OEIL-backfilled separately.

UPDATE committee_work_items c
SET title = lc.title
FROM legislative_carriages lc
WHERE c.legislative_carriage_id = lc.id
  AND (
    c.title ~ '^\*+'
    OR c.title ~* 'ordinary legislative procedure|first reading|second reading'
    OR c.title ~ '\([A-Z]+\)\s+[A-Z]{3,4}\s*$'
    OR c.title ILIKE 'Procedure File:%'
  )
  AND lc.title IS NOT NULL
  AND lc.title !~ '^\*+'
  AND lc.title !~* 'ordinary legislative procedure|first reading'
  AND lc.title !~ '\([A-Z]+\)\s+[A-Z]{3,4}\s*$'
  AND lc.title NOT ILIKE 'Procedure File:%'
  AND length(lc.title) > 12;
