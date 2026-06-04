-- 095: Populate texts_adopted.committees from the linked carriage's lead committee.
--
-- The committees array is enrichment-only and was never filled (0/171 rows), so
-- the In-committee-style PI filter and the committee chips already rendered on the
-- adopted-text card had nothing to work with. 124 adopted texts link to a carriage
-- and 99 of those carriages carry a lead_committee; borrow it so PI filtering and
-- grouping work natively. The ~72 texts with no resolvable committee stay
-- uncategorised (visible under "All committees" only).

UPDATE texts_adopted ta
SET committees = ARRAY[lc.lead_committee]
FROM legislative_carriages lc
WHERE ta.legislative_carriage_id = lc.id
  AND lc.lead_committee IS NOT NULL
  AND lc.lead_committee <> ''
  AND (ta.committees IS NULL OR array_length(ta.committees, 1) IS NULL);
