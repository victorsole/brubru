-- 317: ft_partner_search_announcements keeps no stored bodies, and gets a trigram index on topic_id
-- (27 Oct 2026, the audit of Phase 1 C2).
--
-- The first fill stored body_txt + body_html: about 1,340 bytes a row, some 440 MB of a 956 MB table,
-- though both are composed from the row's own columns (services/scrapers/ft_partner_search.compose_body).
-- /api/v2/funding/partner-announcements now composes them when it answers. The bloated rows made a
-- filtered count read 19,036 blocks (3.9 s for country=ES with organisations without EU projects).
--
-- Topic and programme filters are ILIKE prefix and substring matches (topic=HORIZON-CL5,
-- programme=LIFE): no b-tree serves them, and a count scanned the whole table (3.7 s). A trigram index
-- serves both, as on economy_items.title and gisco_units.name_search.
ALTER TABLE public.ft_partner_search_announcements DROP COLUMN IF EXISTS body_txt;
ALTER TABLE public.ft_partner_search_announcements DROP COLUMN IF EXISTS body_html;
CREATE INDEX IF NOT EXISTS idx_ft_partner_search_announcements_topic_trgm
    ON public.ft_partner_search_announcements USING gin (topic_id gin_trgm_ops);
