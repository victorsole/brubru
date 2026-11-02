-- 323: ft_cascade_calls.opening_date, a cascade call's opening, apart from its publication (2 Nov 2026,
-- Victor's decision; problem register O115). The same as migration 319 for the F&T calls for proposals.
--
-- Until now `published_at` (served as `document_date`) held the portal's `startDate`, the call's OPENING: a
-- forthcoming cascade call carried a date ahead and sat at the top of /funding/opportunities. From now on
-- the ingest stores in `published_at` the earlier of the portal's first publication of the record
-- (`esDA_FirstIngestDate`) and the opening, and the opening here. A call's status keeps reading the opening
-- (ingest_ft_cascade_calls.normalise), which is what the F&T calls lost on 31 Oct (O117).
--
-- No row is written here; the rows were filled once from each row's stored portal record, the opening under
-- brubru.keep_change_signal (the value did not change), the publication date without it (it did).
ALTER TABLE public.ft_cascade_calls ADD COLUMN IF NOT EXISTS opening_date TIMESTAMPTZ;
COMMENT ON COLUMN public.ft_cascade_calls.opening_date IS
    'The portal''s startDate (the call opens). published_at is the earlier of the first publication and this.';
