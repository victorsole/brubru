-- Migration 035: Position Analysis feature
-- Adds:
--   1. user_carriage_tracks.user_position (JSONB) -- per-user stance on a tracked file
--   2. public.file_position_snapshots -- cached aggregate positions for legislative files

BEGIN;

-- 1) Per-user position on a tracked legislative file
ALTER TABLE public.user_carriage_tracks
  ADD COLUMN IF NOT EXISTS user_position JSONB;

-- 2) Cached file-level position snapshots
CREATE TABLE IF NOT EXISTS public.file_position_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  carriage_id UUID NOT NULL REFERENCES public.legislative_carriages(id) ON DELETE CASCADE,
  procedure_ref VARCHAR(50) NOT NULL,

  -- Aggregated positions (JSONB to keep flexible; see services/positions for schema)
  commission_position JSONB,
  parliament_position JSONB,
  council_position JSONB,
  amendment_positions JSONB,  -- article-by-article drill-down when available

  -- Metadata
  data_completeness VARCHAR(16) DEFAULT 'partial',  -- full | partial | minimal
  confidence VARCHAR(16) DEFAULT 'medium',          -- high | medium | low
  sources JSONB,                                    -- {commission_docs: [...], amendments: n, council_events: [...]}

  generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
  expires_at TIMESTAMP WITH TIME ZONE,

  UNIQUE (carriage_id)
);

CREATE INDEX IF NOT EXISTS idx_file_position_snapshots_procedure
  ON public.file_position_snapshots (procedure_ref);
CREATE INDEX IF NOT EXISTS idx_file_position_snapshots_generated
  ON public.file_position_snapshots (generated_at DESC);

-- Enable RLS per memory/feedback_supabase_rls.md
ALTER TABLE public.file_position_snapshots ENABLE ROW LEVEL SECURITY;

COMMIT;
