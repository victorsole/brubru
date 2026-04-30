-- 041 — add source column to eprs_publications so JRC, STOA, ART, ECA
-- publications can land in the same table and be filtered via
-- /api/v1/research-publications?source=jrc|stoa|art|eca|eprs.
-- Created: 30 April 2026.

ALTER TABLE eprs_publications
    ADD COLUMN IF NOT EXISTS source VARCHAR(10) NOT NULL DEFAULT 'eprs',
    ADD COLUMN IF NOT EXISTS doi TEXT,
    ADD COLUMN IF NOT EXISTS eur_number VARCHAR(50);

CREATE INDEX IF NOT EXISTS ix_eprs_publications_source ON eprs_publications(source);

-- Backfill: existing rows are all EPRS (default already 'eprs').
-- Future rows from JRC/STOA/ART/ECA will set source explicitly via the
-- ingestion scripts.
