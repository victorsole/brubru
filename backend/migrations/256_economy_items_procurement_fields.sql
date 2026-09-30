-- 256: procurement fields on economy_items (tender_reference, status, deadline)
--
-- Why: the agency procurement routes under /api/v2/funding (first: Cedefop) carried a
-- tender's reference, status and deadline only inside a composed body, and used the
-- DEADLINE as document_date. Victor, 30 Sep 2026: expose them as their own fields, but
-- reuse the names the funding folder already uses, no new datapoints:
--   tender_reference  as on /funding/ft-calls-for-tenders
--   status            open | forthcoming | closed, as on the Funding & Tenders routes
--   deadline          as on the Funding & Tenders routes (the EXTENDED closing date
--                     when the publisher extended it)
-- document_date goes back to meaning the publication date.
--
-- Nullable and unused by every other body: adding a nullable column with no default is
-- a catalogue-only change in PostgreSQL, instant on the ~588k-row table.
--
-- Identity: a procedure is its reference, not its page address. Cedefop renamed two
-- procedure pages (the old slugs now 301 to the new ones) and each rename created a
-- second row, because the upsert key is (body_code, item_type, public_url). The partial
-- unique index below makes the reference the identity for rows that have one; the writer
-- re-points an existing row to a new URL or type before upserting.

ALTER TABLE public.economy_items
    ADD COLUMN IF NOT EXISTS tender_reference text,
    ADD COLUMN IF NOT EXISTS status           text,
    ADD COLUMN IF NOT EXISTS deadline         timestamptz;

COMMENT ON COLUMN public.economy_items.tender_reference IS
    'Procurement reference as published by the body (e.g. CEDEFOP/2026/OP/0012). Procurement rows only.';
COMMENT ON COLUMN public.economy_items.status IS
    'open | forthcoming | closed, normalised as on the Funding & Tenders routes. Procurement rows only.';
COMMENT ON COLUMN public.economy_items.deadline IS
    'Submission deadline; the extended closing date when the publisher extended it. Procurement rows only.';

-- Merge the two Cedefop duplicates created by page renames. Keep the OLDER id (served
-- longest), move it to the current URL, delete the newer copy. Verified 30 Sep 2026:
-- each old slug answers 301 to the new one.
--   CEDEFOP/2025/OP/0011       keep 483280,  drop 5699321
--   CEDEFOP/2026/LVP/0013-EXA  keep 4235224, drop 5118155
DELETE FROM public.economy_items WHERE id IN (5699321, 5118155) AND body_code = 'cedefop';
UPDATE public.economy_items
   SET public_url = 'https://www.cedefop.europa.eu/en/about-cedefop/public-procurement/graphic-design-layout-services-cedefop-publications-communication-activities'
 WHERE id = 483280 AND body_code = 'cedefop';
UPDATE public.economy_items
   SET public_url = 'https://www.cedefop.europa.eu/en/about-cedefop/public-procurement/ex-ante-publicity-notice-acquisition-provision-voice-telephony-services-telecommunication'
 WHERE id = 4235224 AND body_code = 'cedefop';

-- Existing Cedefop procurement rows already hold the reference in guid, and their
-- document_date IS the closing date (the old reader's design). Move it to deadline;
-- the next sync overwrites document_date with the Official Publication Date.
UPDATE public.economy_items
   SET tender_reference = guid,
       deadline = COALESCE(deadline, document_date)
 WHERE body_code = 'cedefop' AND item_type IN ('tender', 'eoi_call')
   AND tender_reference IS NULL AND guid IS NOT NULL AND guid <> '';

CREATE UNIQUE INDEX IF NOT EXISTS ux_economy_items_body_tender_reference
    ON public.economy_items (body_code, tender_reference)
    WHERE tender_reference IS NOT NULL;
