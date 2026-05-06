-- Migration 053 — extend ft_funded_projects with CORDIS-derived JSONB fields
-- so the EURIO discovery endpoints (3.1-3.5) can return real data.
--
-- Existing ft_funded_projects has flat coordinator + headline fields.
-- These three JSONB columns let /api/v1/discover/eurio/projects/{id}/consortium
-- and /deliverables and /funding return per-project detail without an extra
-- table.

ALTER TABLE ft_funded_projects
    ADD COLUMN IF NOT EXISTS organisations JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS topics JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS euroscivoc JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS legal_basis_details JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS web_links JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS keywords TEXT,
    ADD COLUMN IF NOT EXISTS topic_code VARCHAR(120),
    ADD COLUMN IF NOT EXISTS grant_doi VARCHAR(120);

-- Organisation-name lookup (for /eurio/organisations/{name}/projects)
CREATE INDEX IF NOT EXISTS ix_ftp_orgs_gin
    ON ft_funded_projects USING gin (organisations jsonb_path_ops);

-- Full-text search over title + objective + keywords
CREATE INDEX IF NOT EXISTS ix_ftp_fts
    ON ft_funded_projects USING gin (
        to_tsvector('english',
            coalesce(title, '') || ' ' ||
            coalesce(objective, '') || ' ' ||
            coalesce(keywords, '')
        )
    );

CREATE INDEX IF NOT EXISTS ix_ftp_topic_code ON ft_funded_projects(topic_code);
