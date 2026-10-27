-- 316: ft_partner_search_orgs + ft_partner_search_announcements, the F&T Portal's Partner Search
-- (27 Oct 2026, funding standard Phase 1 C2: organisations looking for partners, including those
-- with no EU money yet).
--
-- Read by scripts/sync_ft_partner_search.py (services/scrapers/ft_partner_search.py) from the EC
-- search index the portal's Partner Search page reads. Organisations only: never a person's profile
-- or a person's announcement. 11,537 organisations had Partner Search on 27 Oct 2026, 6,737 of them
-- with no EU project. An announcement's text is its first 500 characters, as the index holds it,
-- with e-mail addresses, ORCIDs, LinkedIn profile links and telephone numbers removed. Served by /api/v2/funding/partner-announcements
-- and, as activities, by /api/v2/funding/partners.
CREATE TABLE IF NOT EXISTS public.ft_partner_search_orgs (
    pic                  TEXT        PRIMARY KEY,
    name                 TEXT,
    city                 TEXT,
    country              TEXT,                             -- EU style code
    organisation_type    TEXT,                             -- the portal's label (Small or medium-size enterprise ...)
    projects             INTEGER,                          -- the portal's count of the organisation's EU projects
    portal_announcements INTEGER,                          -- the profile's own count (differs from the index's)
    topics               TEXT[],
    public_url           TEXT        NOT NULL,             -- its Partner Search profile on the portal
    first_seen           TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated         TIMESTAMPTZ NOT NULL DEFAULT now(),
    scraped_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ft_partner_search_orgs_country ON public.ft_partner_search_orgs (country);
CREATE INDEX IF NOT EXISTS idx_ft_partner_search_orgs_name_slug ON public.ft_partner_search_orgs
    (country, regexp_replace(lower(name), '[^[:alnum:]]+', '-', 'g'));

CREATE TABLE IF NOT EXISTS public.ft_partner_search_announcements (
    announcement_id      TEXT        PRIMARY KEY,          -- the portal's announcement id
    pic                  TEXT        NOT NULL,
    organisation_name    TEXT,
    country              TEXT,                             -- EU style code
    organisation_type    TEXT,
    expertise            TEXT,                             -- offer | request
    topic_id             TEXT,                             -- HORIZON-CL5-2024-D4-02-05
    topic_ids            TEXT[],
    topic_title          TEXT,
    summary              TEXT,                             -- first 500 characters, contacts removed
    summary_cut          BOOLEAN     NOT NULL DEFAULT false,
    requested_date       DATE,
    indexed_at           TIMESTAMPTZ,                      -- when the portal's index took it
    public_url           TEXT        NOT NULL,             -- the organisation's Partner Search profile
    body_txt             TEXT,
    body_html            TEXT,
    first_seen           TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated         TIMESTAMPTZ NOT NULL DEFAULT now(),
    scraped_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ft_partner_search_announcements_pic ON public.ft_partner_search_announcements (pic);
CREATE INDEX IF NOT EXISTS idx_ft_partner_search_announcements_topic ON public.ft_partner_search_announcements (topic_id);
CREATE INDEX IF NOT EXISTS idx_ft_partner_search_announcements_requested ON public.ft_partner_search_announcements (requested_date);
CREATE INDEX IF NOT EXISTS idx_ft_partner_search_announcements_last_updated ON public.ft_partner_search_announcements (last_updated);
CREATE INDEX IF NOT EXISTS idx_ft_partner_search_announcements_country ON public.ft_partner_search_announcements (country);
CREATE INDEX IF NOT EXISTS idx_ft_partner_search_announcements_fts ON public.ft_partner_search_announcements
    USING gin (to_tsvector('english', coalesce(topic_title, '') || ' ' || coalesce(summary, '')));

ALTER TABLE public.ft_partner_search_orgs ENABLE ROW LEVEL SECURITY;
CREATE POLICY ft_partner_search_orgs_public_read ON public.ft_partner_search_orgs
    FOR SELECT TO anon, authenticated USING (true);
REVOKE ALL ON public.ft_partner_search_orgs FROM anon, authenticated;
GRANT SELECT ON public.ft_partner_search_orgs TO anon, authenticated;
GRANT ALL ON public.ft_partner_search_orgs TO service_role;

ALTER TABLE public.ft_partner_search_announcements ENABLE ROW LEVEL SECURITY;
CREATE POLICY ft_partner_search_announcements_public_read ON public.ft_partner_search_announcements
    FOR SELECT TO anon, authenticated USING (true);
REVOKE ALL ON public.ft_partner_search_announcements FROM anon, authenticated;
GRANT SELECT ON public.ft_partner_search_announcements TO anon, authenticated;
GRANT ALL ON public.ft_partner_search_announcements TO service_role;

CREATE TRIGGER trg_ft_partner_search_orgs_touch BEFORE UPDATE ON public.ft_partner_search_orgs
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen');
CREATE TRIGGER trg_ft_partner_search_announcements_touch BEFORE UPDATE ON public.ft_partner_search_announcements
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen');
