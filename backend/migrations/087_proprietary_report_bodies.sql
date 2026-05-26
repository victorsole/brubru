-- Migration 087: proprietary_report_bodies — body cache for the
-- "Brubru Proprietary Databases" API domain (/api/v2/proprietary/*).
--
-- WHY: the rendered HTML for canon/deep-dive reports and Catalan translations
-- lives as static files on SiteGround, and the Railway backend CANNOT fetch
-- brubru.beresol.eu (the shared host blocks the datacenter egress IP — proven:
-- both the canon and the v1 catalan body fetches return empty on prod while
-- serving fine to residential IPs). frontend/public is not in the backend
-- build context either. So we cache the rendered bodies here, seeded LOCALLY
-- (where the files exist) by scripts/seed_proprietary_bodies.py, and the API
-- serves bodies from this table — no runtime SiteGround fetch.
--
-- Guides are NOT stored here: their markdown lives in the backend repo and is
-- rendered to HTML on the fly.
--
-- Public-read reference data. Mandatory Data-API order:
-- CREATE -> ENABLE RLS -> POLICY -> GRANT (see CLAUDE.md).

CREATE TABLE IF NOT EXISTS public.proprietary_report_bodies (
    source       TEXT        NOT NULL,           -- 'canon' | 'catalan'
    ref          TEXT        NOT NULL,           -- canon slug | catalan CELEX
    lang         TEXT        NOT NULL DEFAULT 'en', -- en/es/ca/fr/it/nl (catalan = 'ca')
    body_html    TEXT,
    body_txt     TEXT,
    char_count   INTEGER     NOT NULL DEFAULT 0, -- len(body_txt)
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source, ref, lang)
);

COMMENT ON TABLE public.proprietary_report_bodies IS
  'Body cache for /api/v2/proprietary/{canon,catalan}. Seeded locally from the rendered HTML (Railway cannot fetch SiteGround). Safe to re-seed.';

CREATE INDEX IF NOT EXISTS proprietary_bodies_source_ref_idx
    ON public.proprietary_report_bodies (source, ref);

ALTER TABLE public.proprietary_report_bodies ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS proprietary_bodies_public_read ON public.proprietary_report_bodies;
CREATE POLICY proprietary_bodies_public_read ON public.proprietary_report_bodies
    FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS proprietary_bodies_service_all ON public.proprietary_report_bodies;
CREATE POLICY proprietary_bodies_service_all ON public.proprietary_report_bodies
    FOR ALL TO service_role USING (true) WITH CHECK (true);

GRANT SELECT ON public.proprietary_report_bodies TO anon, authenticated;
GRANT ALL    ON public.proprietary_report_bodies TO service_role;
