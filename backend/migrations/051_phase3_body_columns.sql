-- Migration 051: Phase-3 body-text columns
-- Created: 2026-05-03
-- Purpose: Close the CC-2(b) Phase-3 content gap by adding text_body columns to
-- the tables Jordi flagged for body extraction. Backfilled via Cellar API
-- (commission_documents, secondary_acts — both have CELEX) by
-- backend/scripts/backfill_body_text.py with --kind register-docs / acts.

ALTER TABLE public.commission_documents
    ADD COLUMN IF NOT EXISTS text_body TEXT;

ALTER TABLE public.secondary_acts
    ADD COLUMN IF NOT EXISTS text_body TEXT;

CREATE INDEX IF NOT EXISTS idx_commission_documents_has_body
    ON public.commission_documents ((text_body IS NOT NULL))
    WHERE text_body IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_secondary_acts_has_body
    ON public.secondary_acts ((text_body IS NOT NULL))
    WHERE text_body IS NOT NULL;
