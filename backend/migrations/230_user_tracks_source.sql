-- 230: record WHO put a row in a tracking table -- the user, or us.
--
-- WHY
-- ---
-- /users measured on 10 September 2026 that 755 of 932 non-internal tracked items
-- (81%), across 35 of 43 holders, had their ENTIRE tracking written in <=2 distinct
-- minutes. That is a bulk write, not a person clicking. The clearest case is the
-- largest holding on the platform: julian.ramirez@gbsb.global shows 111 tracked
-- carriages written in exactly two minutes -- 7 on 26 Aug 09:50 (dormant-claim
-- provisioning) and 104 on 7 Sep 14:00 (post-claim populate from Policy Interests).
-- He has never tracked anything himself.
--
-- Previous /users runs read these tables as an engagement signal. They are mostly
-- not one, and nothing in the row said so. This is the seed-fixture lesson applied
-- to engagement data: our own writes were indistinguishable from user actions at
-- query time, so they were counted as users. See
-- memory/feedback_seed_fixtures_contaminate_prod.md -- that incident ended with
-- "better long-term pattern: add the column at table-creation time". These tables
-- predate the lesson, so it is added now.
--
-- WHAT
-- ----
-- A nullable `source` on all six user_*_tracks tables:
--
--   'user'         the user chose THIS item (a track button, or setting a position
--                  on a specific file, which auto-tracks it)
--   'provisioned'  we wrote it: dormant-claim provisioning, or the Policy-Interest
--                  auto-populate that picks the items by algorithm
--   NULL           written before this migration; provenance genuinely unknown
--
-- THREE STATES, DELIBERATELY. The original proposal was `DEFAULT 'user'` on the
-- column, which in PostgreSQL 11+ backfills every existing row -- stamping all 932
-- historic rows as user-chosen and hard-coding the exact false reading this column
-- exists to remove. So the column is added WITHOUT a default (existing rows land
-- NULL = unknown) and the default is set afterwards, which applies only to new
-- rows. "Untested" must not be able to read as "healthy":
-- memory/feedback_zero_denominator_is_not_a_pass.md.
--
-- The historic rows are NOT guessed here. A backfill exists as a separate,
-- dry-runnable script with its rule stated and its count reported before it writes
-- (scripts/backfill_track_source.py), so the judgement is visible and reversible
-- rather than buried in a migration.
--
-- NOT a boolean. 'provisioned' will need sub-kinds later (dormant-claim vs
-- PI-autopopulate vs a future digest action) and a boolean cannot grow one.

ALTER TABLE public.user_carriage_tracks       ADD COLUMN IF NOT EXISTS source TEXT;
ALTER TABLE public.user_commission_doc_tracks ADD COLUMN IF NOT EXISTS source TEXT;
ALTER TABLE public.user_committee_work_tracks ADD COLUMN IF NOT EXISTS source TEXT;
ALTER TABLE public.user_consultation_tracks   ADD COLUMN IF NOT EXISTS source TEXT;
ALTER TABLE public.user_text_adopted_tracks   ADD COLUMN IF NOT EXISTS source TEXT;
ALTER TABLE public.user_vote_tracks           ADD COLUMN IF NOT EXISTS source TEXT;

-- Set the default only AFTER the column exists, so existing rows keep NULL.
ALTER TABLE public.user_carriage_tracks       ALTER COLUMN source SET DEFAULT 'user';
ALTER TABLE public.user_commission_doc_tracks ALTER COLUMN source SET DEFAULT 'user';
ALTER TABLE public.user_committee_work_tracks ALTER COLUMN source SET DEFAULT 'user';
ALTER TABLE public.user_consultation_tracks   ALTER COLUMN source SET DEFAULT 'user';
ALTER TABLE public.user_text_adopted_tracks   ALTER COLUMN source SET DEFAULT 'user';
ALTER TABLE public.user_vote_tracks           ALTER COLUMN source SET DEFAULT 'user';

-- A typo in a writer must fail loudly, not create a third silent bucket that then
-- gets counted as "unknown" alongside genuine history.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'user_carriage_tracks','user_commission_doc_tracks','user_committee_work_tracks',
    'user_consultation_tracks','user_text_adopted_tracks','user_vote_tracks'
  ] LOOP
    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conname = t || '_source_check'
        AND conrelid = ('public.' || t)::regclass
    ) THEN
      EXECUTE format(
        'ALTER TABLE public.%I ADD CONSTRAINT %I CHECK (source IS NULL OR source IN (''user'',''provisioned''))',
        t, t || '_source_check');
    END IF;
  END LOOP;
END $$;

COMMENT ON COLUMN public.user_carriage_tracks.source IS
    'Who created this track: ''user'' (they chose this item), ''provisioned'' (we '
    'wrote it -- dormant-claim or Policy-Interest auto-populate), NULL (written '
    'before migration 230, provenance unknown). NEVER read NULL as ''user''. Any '
    'engagement metric must exclude ''provisioned'' and report NULL separately.';
COMMENT ON COLUMN public.user_commission_doc_tracks.source IS 'See user_carriage_tracks.source.';
COMMENT ON COLUMN public.user_committee_work_tracks.source IS 'See user_carriage_tracks.source.';
COMMENT ON COLUMN public.user_consultation_tracks.source IS 'See user_carriage_tracks.source.';
COMMENT ON COLUMN public.user_text_adopted_tracks.source IS 'See user_carriage_tracks.source.';
COMMENT ON COLUMN public.user_vote_tracks.source IS 'See user_carriage_tracks.source.';

-- The access pattern is "this user's genuinely self-chosen items", i.e. filter on
-- user_id + source together, so index the pair rather than source alone.
CREATE INDEX IF NOT EXISTS idx_user_carriage_tracks_user_source       ON public.user_carriage_tracks (user_id, source);
CREATE INDEX IF NOT EXISTS idx_user_commission_doc_tracks_user_source ON public.user_commission_doc_tracks (user_id, source);
CREATE INDEX IF NOT EXISTS idx_user_committee_work_tracks_user_source ON public.user_committee_work_tracks (user_id, source);
CREATE INDEX IF NOT EXISTS idx_user_consultation_tracks_user_source   ON public.user_consultation_tracks (user_id, source);
CREATE INDEX IF NOT EXISTS idx_user_text_adopted_tracks_user_source   ON public.user_text_adopted_tracks (user_id, source);
CREATE INDEX IF NOT EXISTS idx_user_vote_tracks_user_source           ON public.user_vote_tracks (user_id, source);

-- Supabase Data API grants: adding a column does not change table-level grants and
-- RLS/policies are untouched here, so nothing further is required. Recorded
-- explicitly so the omission reads as deliberate rather than forgotten (the default
-- grant was removed 30 Oct 2026 and a replay breaks without them on NEW tables).
