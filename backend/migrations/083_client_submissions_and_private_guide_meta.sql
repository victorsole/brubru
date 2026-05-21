-- Migration 083: client_submissions table + meta_json on private_guides.
--
-- Background:
--   Blue-tier clients (TAS Europrojects is the first) share an internal
--   tracker (Excel) of every bid they have submitted: contracting authority,
--   country, sector, lot, outcome, comments. We ingest this into the
--   `client_submissions` table keyed by private_guide_slug so the chat,
--   Tenderator and the win-rate scorecard endpoint can read it.
--
--   The new `meta_json` column on `private_guides` stores per-slug metadata
--   (pursuits filter, organisation logo, linked users) so the Tenderator
--   pre-filter and the scorecard endpoint don't need to read disk files.
--   The local _meta.json on disk is the source of truth; the
--   sync_private_guides_to_db.py script writes one canonical row per slug
--   with filename='_meta.json' carrying the JSON in this column.
--
-- Scope:
--   - public.client_submissions: one row per past bid, keyed by slug.
--   - public.private_guides.meta_json: nullable JSONB column.
--
-- Backfill: handled in scripts/ingest_client_submissions.py (Excel -> rows)
-- + scripts/sync_private_guides_to_db.py (now reads _meta.json).
--
-- Same RLS / GRANT pattern as user_documents (CLAUDE.md hard rule).

BEGIN;

-- ===========================================================================
-- Step 1: client_submissions table
-- ===========================================================================

CREATE TABLE IF NOT EXISTS public.client_submissions (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug               TEXT NOT NULL,
  external_ref       TEXT,
  project_title      TEXT NOT NULL,
  contracting_authority TEXT,
  country            TEXT,
  region             TEXT,
  programme          TEXT,
  lot                TEXT,
  sector             TEXT,
  submission_date    DATE,
  submission_status  TEXT,
  leading_partner    TEXT,
  is_lead            BOOLEAN DEFAULT FALSE,
  outcome            TEXT NOT NULL DEFAULT 'pending'
                      CHECK (outcome IN ('awarded','not_awarded','pending','cancelled','withdrawn')),
  points_obtained    NUMERIC(6,2),
  points_winner      NUMERIC(6,2),
  comments           TEXT,
  budget_eur         NUMERIC(15,2),
  client_margin_eur  NUMERIC(15,2),
  source             TEXT NOT NULL DEFAULT 'manual',
  source_file        TEXT,
  raw_payload        JSONB,
  is_test            BOOLEAN NOT NULL DEFAULT FALSE,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_client_submissions_slug
  ON public.client_submissions (slug);
CREATE INDEX IF NOT EXISTS idx_client_submissions_slug_outcome
  ON public.client_submissions (slug, outcome);
CREATE INDEX IF NOT EXISTS idx_client_submissions_ca
  ON public.client_submissions (slug, contracting_authority);
CREATE INDEX IF NOT EXISTS idx_client_submissions_country
  ON public.client_submissions (slug, country);

ALTER TABLE public.client_submissions ENABLE ROW LEVEL SECURITY;

-- Service role only: this is internal-client data, never directly read by
-- end users. The /api/tenders/* endpoints sit behind require_blue_tier and
-- proxy the data after joining on private_guide_slug.
CREATE POLICY client_submissions_service_role_all ON public.client_submissions
  FOR ALL TO service_role USING (true) WITH CHECK (true);

GRANT SELECT ON public.client_submissions TO authenticated;
GRANT ALL    ON public.client_submissions TO service_role;

-- ===========================================================================
-- Step 2: meta_json column on private_guides
-- ===========================================================================

ALTER TABLE public.private_guides
  ADD COLUMN IF NOT EXISTS meta_json JSONB;

COMMENT ON COLUMN public.private_guides.meta_json IS
  'Per-slug metadata mirrored from the local _meta.json file. Stored on the canonical filename=''_meta.json'' row. Used by Tenderator pre-filter and client-scorecard endpoint.';

COMMIT;
