-- Migration 080: Defensive DB-side defaults + CHECK constraint on user_documents.
--
-- Background:
--   On 21 May 2026 a bootstrap script seeded 6 user_documents rows for a new
--   user via raw SQL INSERT without setting view_count. The model declares
--   Column(Integer, default=0), but that default is ORM-side, NOT a Postgres
--   DEFAULT, so the column landed NULL. Pydantic UserDocumentResponse declares
--   view_count: int (non-Optional), rejected the row at response serialization,
--   /api/documents returned 500, and the My EU Bubble frontend white-screened
--   for the user (no error boundary above useBubble).
--
--   This was the second documented occurrence of the same class of bug
--   (Guido Maria Valletta had the same NULL trap plus invalid document_type
--   values 'mep_letter' and 'commission_email'). See
--   memory/feedback_raw_insert_orm_defaults.md.
--
-- This migration pushes the defaults to the database so any future raw INSERT
-- gets the right value, and adds a CHECK on document_type to refuse values
-- outside the Pydantic allowlist at the database boundary instead of at the
-- API serialization layer.
--
-- Pre-flight (verified 21 May 2026 before writing this migration):
--   - 0 rows with view_count IS NULL
--   - 0 rows with version IS NULL
--   - 0 rows with is_private IS NULL
--   - 0 rows with include_in_ai_context IS NULL
--   - 0 rows with document_type IS NULL
--   - 45 rows with is_featured IS NULL (backfilled inside this migration)
--   - 0 rows with document_type NOT IN the allowlist
--
-- All ALTER COLUMN ... SET DEFAULT statements are idempotent. The CHECK and
-- the SET NOT NULL stanzas will fail loudly if any future row violates them,
-- which is the desired behaviour.

BEGIN;

-- Step 1: backfill is_featured NULLs to FALSE so we can set NOT NULL.
UPDATE public.user_documents SET is_featured = FALSE WHERE is_featured IS NULL;

-- Step 2: DB-side defaults for integer counters.
ALTER TABLE public.user_documents ALTER COLUMN view_count SET DEFAULT 0;
ALTER TABLE public.user_documents ALTER COLUMN version    SET DEFAULT 1;

-- Step 3: DB-side defaults for boolean flags (model defaults were ORM-side only).
ALTER TABLE public.user_documents ALTER COLUMN is_private            SET DEFAULT TRUE;
ALTER TABLE public.user_documents ALTER COLUMN is_featured           SET DEFAULT FALSE;
ALTER TABLE public.user_documents ALTER COLUMN include_in_ai_context SET DEFAULT FALSE;

-- Step 4: NOT NULL on the columns whose Pydantic response model is non-Optional.
ALTER TABLE public.user_documents ALTER COLUMN view_count            SET NOT NULL;
ALTER TABLE public.user_documents ALTER COLUMN version               SET NOT NULL;
ALTER TABLE public.user_documents ALTER COLUMN is_private            SET NOT NULL;
ALTER TABLE public.user_documents ALTER COLUMN is_featured           SET NOT NULL;
ALTER TABLE public.user_documents ALTER COLUMN include_in_ai_context SET NOT NULL;

-- Step 5: CHECK constraint pinning document_type to the Pydantic allowlist.
-- Pydantic allowlist source: backend/schemas/user_document_schemas.py
--   allowed_types = ['amendment', 'analysis', 'strategy', 'note', 'uploaded']
-- If a new document_type is introduced, update the Pydantic validator AND
-- this CHECK in a single migration. Do not loosen one without the other.
ALTER TABLE public.user_documents
    DROP CONSTRAINT IF EXISTS user_documents_document_type_check;
ALTER TABLE public.user_documents
    ADD CONSTRAINT user_documents_document_type_check
    CHECK (document_type IN ('amendment', 'analysis', 'strategy', 'note', 'uploaded'));

-- Step 6: COMMENT for future readers.
COMMENT ON CONSTRAINT user_documents_document_type_check ON public.user_documents IS 'Pins document_type to the Pydantic UserDocumentBase allowlist. See migration 080 and memory/feedback_raw_insert_orm_defaults.md. Update Pydantic validator AND this constraint together; never one alone.';

COMMIT;
