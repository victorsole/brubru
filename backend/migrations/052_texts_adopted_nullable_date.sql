-- Migration 052: Drop NOT NULL on texts_adopted.adoption_date
-- Created: 2026-05-03
-- Purpose: The /api/v1/texts-submitted endpoint queries texts_adopted WHERE
-- adoption_date IS NULL — but the column was NOT NULL, so the endpoint could
-- never return rows. Allowing NULLs lets us insert "tabled for plenary, not
-- yet voted" rows from EP plenary's texts-submitted page (committee reports
-- with A-NN-YYYY-XXXX refs awaiting their plenary vote).

ALTER TABLE public.texts_adopted
    ALTER COLUMN adoption_date DROP NOT NULL;
