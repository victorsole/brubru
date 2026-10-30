-- 319: ft_calls_for_proposals.opening_date, a call's opening, apart from its publication (30 Oct 2026,
-- Victor's decision; problem register O95).
--
-- Until now `published_at` (served as `document_date`) held the portal's `startDate`, the call's
-- OPENING: every forthcoming call carried a date in the future (264 on 28 Oct 2026, up to Oct 2027),
-- so order=recent listed openings planned for 2027 first. From now on the ingest stores in
-- `published_at` the earlier of the portal's first publication of the record (`esDA_FirstIngestDate`)
-- and the opening, and the opening here. `esDA_FirstIngestDate` is a re-indexing stamp on older records
-- (22 Nov 2024 on calls of 2021-2024, after their own deadline on ERC-2025-STG), which is why the
-- earlier of the two is kept, never the first-ingest date alone.
--
-- No row is written here: the column starts empty and the API serves opening_date as
-- coalesce(opening_date, published_at), which is the opening on every row the ingest has not re-read
-- (their published_at still holds it). Copying it into 6,245 rows would have moved every call's
-- `updated_date` (the change trigger) for a value that did not change.
ALTER TABLE public.ft_calls_for_proposals ADD COLUMN IF NOT EXISTS opening_date TIMESTAMP;
COMMENT ON COLUMN public.ft_calls_for_proposals.opening_date IS
    'The portal''s startDate (the call opens), UTC. published_at is the earlier of the first publication and this.';
