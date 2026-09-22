-- 234: real "created" and "updated" dates for incremental sync (22 Sep 2026).
--
-- Why: a partner (GovClipping) syncs the API every morning and reported that six list
-- endpoints carried no usable date and no date filter, so the only way to find what
-- changed was to re-read every page (MEPs, commissioners, EU officials, infringements,
-- calls for proposals, calls for tenders). Two of the tables had a date that LOOKED
-- usable but was not: the funding writers set `last_updated = NOW()` on every upsert,
-- so all 2,918 calls carried the time of the last sync, changed or not.
--
-- The rule, enforced by ONE trigger function so no writer has to remember it:
--   * the created column is set on INSERT and can never move afterwards;
--   * `content_updated_at` moves only when a content column actually changes.
--     Bookkeeping columns (last seen, fetched, scraped) are named per table and ignored.
--
-- MEPs and commissioners are not stored as rows (live EP API / hand-curated JSON), so
-- they get `api_record_snapshots`: one row per record with a hash of its content,
-- written daily by scripts/snapshot_live_registers.py.

CREATE OR REPLACE FUNCTION public.brubru_track_content_change()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    created_col text := TG_ARGV[0];
    ignored     text[] := COALESCE(TG_ARGV[1:TG_NARGS - 1], '{}'::text[]);
BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.content_updated_at := COALESCE(NEW.content_updated_at, now());
        RETURN NEW;
    END IF;
    -- The created column never moves once the row exists.
    NEW := jsonb_populate_record(NEW, jsonb_build_object(created_col, to_jsonb(OLD) -> created_col));
    IF (to_jsonb(NEW) - ignored - created_col - 'content_updated_at')
       IS DISTINCT FROM
       (to_jsonb(OLD) - ignored - created_col - 'content_updated_at') THEN
        NEW.content_updated_at := now();
    ELSE
        NEW.content_updated_at := OLD.content_updated_at;
    END IF;
    RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------- funding calls
-- scraped_at and last_updated are rewritten on every upsert, so neither says when a
-- call was first seen. The earliest value we can prove is the one we keep; rows
-- ingested before this migration therefore carry a first-seen date that is no
-- EARLIER than the truth.
ALTER TABLE public.ft_calls_for_proposals
    ADD COLUMN IF NOT EXISTS first_seen_at      timestamptz,
    ADD COLUMN IF NOT EXISTS content_updated_at timestamptz;
UPDATE public.ft_calls_for_proposals
   SET first_seen_at = COALESCE(first_seen_at, LEAST(scraped_at, last_updated) AT TIME ZONE 'UTC', now()),
       content_updated_at = COALESCE(content_updated_at, LEAST(scraped_at, last_updated) AT TIME ZONE 'UTC', now());
ALTER TABLE public.ft_calls_for_proposals
    ALTER COLUMN first_seen_at SET DEFAULT now(),
    ALTER COLUMN first_seen_at SET NOT NULL,
    ALTER COLUMN content_updated_at SET NOT NULL;

ALTER TABLE public.ft_calls_for_tenders
    ADD COLUMN IF NOT EXISTS first_seen_at      timestamptz,
    ADD COLUMN IF NOT EXISTS content_updated_at timestamptz;
UPDATE public.ft_calls_for_tenders
   SET first_seen_at = COALESCE(first_seen_at, LEAST(scraped_at, last_updated) AT TIME ZONE 'UTC', now()),
       content_updated_at = COALESCE(content_updated_at, LEAST(scraped_at, last_updated) AT TIME ZONE 'UTC', now());
ALTER TABLE public.ft_calls_for_tenders
    ALTER COLUMN first_seen_at SET DEFAULT now(),
    ALTER COLUMN first_seen_at SET NOT NULL,
    ALTER COLUMN content_updated_at SET NOT NULL;

DROP TRIGGER IF EXISTS trg_ft_calls_for_proposals_changes ON public.ft_calls_for_proposals;
CREATE TRIGGER trg_ft_calls_for_proposals_changes
    BEFORE INSERT OR UPDATE ON public.ft_calls_for_proposals
    FOR EACH ROW EXECUTE FUNCTION public.brubru_track_content_change('first_seen_at', 'scraped_at', 'last_updated');
DROP TRIGGER IF EXISTS trg_ft_calls_for_tenders_changes ON public.ft_calls_for_tenders;
CREATE TRIGGER trg_ft_calls_for_tenders_changes
    BEFORE INSERT OR UPDATE ON public.ft_calls_for_tenders
    FOR EACH ROW EXECUTE FUNCTION public.brubru_track_content_change('first_seen_at', 'scraped_at', 'last_updated');

CREATE INDEX IF NOT EXISTS ix_ftc_content_updated ON public.ft_calls_for_proposals (content_updated_at, id);
CREATE INDEX IF NOT EXISTS ix_ftc_first_seen      ON public.ft_calls_for_proposals (first_seen_at, id);
CREATE INDEX IF NOT EXISTS ix_ftt_content_updated ON public.ft_calls_for_tenders (content_updated_at, id);
CREATE INDEX IF NOT EXISTS ix_ftt_first_seen      ON public.ft_calls_for_tenders (first_seen_at, id);

-- ---------------------------------------------------------------- EU officials
-- removed_at: set by the sync when an official is no longer in the directory, so a
-- partner syncing incrementally learns about departures instead of keeping them.
ALTER TABLE public.who_is_who_officials
    ADD COLUMN IF NOT EXISTS content_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS removed_at         timestamptz;
UPDATE public.who_is_who_officials SET content_updated_at = COALESCE(content_updated_at, fetched_at, first_seen);
ALTER TABLE public.who_is_who_officials ALTER COLUMN content_updated_at SET NOT NULL;

DROP TRIGGER IF EXISTS trg_who_is_who_officials_changes ON public.who_is_who_officials;
CREATE TRIGGER trg_who_is_who_officials_changes
    BEFORE INSERT OR UPDATE ON public.who_is_who_officials
    FOR EACH ROW EXECUTE FUNCTION public.brubru_track_content_change('first_seen', 'fetched_at');

CREATE INDEX IF NOT EXISTS ix_wiw_off_content_updated ON public.who_is_who_officials (content_updated_at, id);
CREATE INDEX IF NOT EXISTS ix_wiw_off_first_seen      ON public.who_is_who_officials (first_seen, id);

-- ---------------------------------------------------------------- infringements
ALTER TABLE public.infringement_cases     ADD COLUMN IF NOT EXISTS content_updated_at timestamptz;
ALTER TABLE public.infringement_decisions ADD COLUMN IF NOT EXISTS content_updated_at timestamptz;
UPDATE public.infringement_cases     SET content_updated_at = COALESCE(content_updated_at, creation_date);
UPDATE public.infringement_decisions SET content_updated_at = COALESCE(content_updated_at, creation_date);
ALTER TABLE public.infringement_cases     ALTER COLUMN content_updated_at SET NOT NULL;
ALTER TABLE public.infringement_decisions ALTER COLUMN content_updated_at SET NOT NULL;

DROP TRIGGER IF EXISTS trg_infringement_cases_changes ON public.infringement_cases;
CREATE TRIGGER trg_infringement_cases_changes
    BEFORE INSERT OR UPDATE ON public.infringement_cases
    FOR EACH ROW EXECUTE FUNCTION public.brubru_track_content_change('creation_date', 'last_seen_at');
DROP TRIGGER IF EXISTS trg_infringement_decisions_changes ON public.infringement_decisions;
CREATE TRIGGER trg_infringement_decisions_changes
    BEFORE INSERT OR UPDATE ON public.infringement_decisions
    FOR EACH ROW EXECUTE FUNCTION public.brubru_track_content_change('creation_date', 'last_seen_at');

CREATE INDEX IF NOT EXISTS ix_infringement_cases_content_updated     ON public.infringement_cases (content_updated_at, id);
CREATE INDEX IF NOT EXISTS ix_infringement_cases_creation            ON public.infringement_cases (creation_date, id);
CREATE INDEX IF NOT EXISTS ix_infringement_decisions_content_updated ON public.infringement_decisions (content_updated_at, id);
CREATE INDEX IF NOT EXISTS ix_infringement_decisions_creation        ON public.infringement_decisions (creation_date, id);

-- ---------------------------------------------------------------- live registers
CREATE TABLE IF NOT EXISTS public.api_record_snapshots (
    dataset            text        NOT NULL,
    record_key         text        NOT NULL,
    payload            jsonb       NOT NULL,
    content_hash       text        NOT NULL,
    first_seen_at      timestamptz NOT NULL DEFAULT now(),
    content_updated_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at       timestamptz NOT NULL DEFAULT now(),
    removed_at         timestamptz,
    PRIMARY KEY (dataset, record_key)
);
CREATE INDEX IF NOT EXISTS ix_api_record_snapshots_updated ON public.api_record_snapshots (dataset, content_updated_at);

ALTER TABLE public.api_record_snapshots ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS api_record_snapshots_read ON public.api_record_snapshots;
CREATE POLICY api_record_snapshots_read ON public.api_record_snapshots
    FOR SELECT TO anon, authenticated USING (true);
DROP POLICY IF EXISTS api_record_snapshots_service_all ON public.api_record_snapshots;
CREATE POLICY api_record_snapshots_service_all ON public.api_record_snapshots
    FOR ALL TO service_role USING (true) WITH CHECK (true);
GRANT SELECT ON public.api_record_snapshots TO anon, authenticated;
GRANT ALL    ON public.api_record_snapshots TO service_role;
