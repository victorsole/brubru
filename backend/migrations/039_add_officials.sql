-- 039 — eu_officials registry table for /api/v1/officials.
-- Backs the W5 P2 deliverable from Thursday brief 1.5 (EU Who is Who).
-- Created: 25 April 2026.

CREATE TABLE IF NOT EXISTS eu_officials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    slug VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    title VARCHAR(255),
    role VARCHAR(255),

    institution_slug VARCHAR(100) NOT NULL,
    dg VARCHAR(20),
    cabinet VARCHAR(100),

    country VARCHAR(3),
    city VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(50),

    bio_url TEXT,
    photo_url TEXT,
    social_links JSONB DEFAULT '{}'::jsonb,

    appointed_date DATE,
    term_end_date DATE,

    portfolio TEXT,
    policy_areas TEXT[] DEFAULT '{}',

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    scraped_at TIMESTAMP DEFAULT NOW(),
    first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_eu_officials_slug ON eu_officials(slug);
CREATE INDEX IF NOT EXISTS ix_eu_officials_institution ON eu_officials(institution_slug);
CREATE INDEX IF NOT EXISTS ix_eu_officials_dg ON eu_officials(dg);
CREATE INDEX IF NOT EXISTS ix_eu_officials_active ON eu_officials(is_active);

ALTER TABLE eu_officials ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
    EXECUTE 'CREATE POLICY allow_read_eu_officials ON eu_officials FOR SELECT USING (true)';
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
