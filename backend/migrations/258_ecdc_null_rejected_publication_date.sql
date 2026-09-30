-- 258: clear the one ECDC document_date that is really the old deadline
--
-- Migration 257 copied the stored document_date (then the DEADLINE) into deadline but
-- left it in document_date too. The backfill writes document_date only when the page
-- gives a plausible publication date, and the upsert never regresses a value to NULL,
-- so where the reader found none the old deadline stayed as the "publication" date.
-- Checked 30 Sep 2026: exactly one ECDC row (its only date, article:published_time
-- 2025-12-16, falls after its 2025-02-28 deadline and was rejected). The one Cedefop row
-- whose document_date equals its deadline is genuine: Cedefop publishes 30/09/2014 as
-- both its Official Publication Date and its closing date.
--
-- Lesson for the next body: when moving document_date to deadline, also set
-- document_date to NULL, so the backfill starts from nothing rather than from the deadline.
UPDATE public.economy_items
   SET document_date = NULL
 WHERE id = 485117 AND body_code = 'ecdc'
   AND tender_reference = 'ECDC/2025/MVP/0024-EXA - RMS/260882'
   AND document_date = deadline;
