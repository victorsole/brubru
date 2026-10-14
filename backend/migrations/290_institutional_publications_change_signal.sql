-- 290: institutional_publications gets a change signal.
--
-- /api/v2/council/council-documents, /api/v1/publications and the press-release list
-- answered ?updated_from= off fetched_at, the ingestion anchor that every upsert sets to
-- now() whether or not anything changed. The items carried updated_date = null (the
-- table's updated_date column is the source's own, and no writer fills it), so a client
-- filtered on a value it could not see. Found 14 Oct 2026 auditing GovClipping's
-- council-documents request: 672 of 672 items with updated_date null.
--
-- updated_at is the change signal, kept by brubru_touch_if_changed (migration 245), the
-- one place every writer passes through: it moves when a content column changes and is
-- held otherwise. fetched_at keeps moving every run (it answers "is this feed alive") and
-- created_at is pinned.
--
-- Existing rows start at fetched_at: their last real change is unknown, and fetched_at is
-- never earlier than it, so a client re-reads a row it may already hold rather than
-- missing one that changed.

ALTER TABLE institutional_publications ADD COLUMN IF NOT EXISTS updated_at timestamptz;
UPDATE institutional_publications SET updated_at = fetched_at WHERE updated_at IS NULL;
ALTER TABLE institutional_publications ALTER COLUMN updated_at SET DEFAULT now();
ALTER TABLE institutional_publications ALTER COLUMN updated_at SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_inst_pub_updated_at ON institutional_publications (updated_at DESC);

DROP TRIGGER IF EXISTS trg_institutional_publications_touch ON institutional_publications;
CREATE TRIGGER trg_institutional_publications_touch BEFORE UPDATE ON institutional_publications
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', 'fetched_at', 'created_at');
