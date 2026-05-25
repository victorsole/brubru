-- Migration 085: law_xref — the cross-reference cache behind /api/v2/legislative/eur-lex/laws/{celex}/xref
--
-- One row per CELEX holding the productised join graph: ELI, OJ ref, the
-- legislative procedure that produced it, EuroVoc topics, legal basis,
-- in-force flag, and relationship counts. Lazily populated on each /xref call
-- (write is best-effort; the endpoint works even before this table exists) and
-- backfillable in bulk over eu_laws. This is the same join key flagged in
-- memory/reference_eurlex_waf_and_join.md.
--
-- Public-read reference cache (cross-reference metadata is public legal data).
-- Follows the mandatory Data-API order: CREATE -> ENABLE RLS -> POLICY -> GRANT
-- (see CLAUDE.md "Supabase Data API grants are mandatory").

CREATE TABLE IF NOT EXISTS public.law_xref (
    celex              VARCHAR(30) PRIMARY KEY,
    eli                TEXT,
    oj_reference       TEXT,
    procedure_ref      TEXT,
    resource_type      TEXT,
    in_force           BOOLEAN,
    document_date      DATE,
    eurovoc            JSONB       NOT NULL DEFAULT '[]'::jsonb,
    legal_basis        JSONB       NOT NULL DEFAULT '[]'::jsonb,
    authors            JSONB       NOT NULL DEFAULT '[]'::jsonb,
    relation_counts    JSONB       NOT NULL DEFAULT '{}'::jsonb,
    relation_total     INTEGER     NOT NULL DEFAULT 0,
    computed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.law_xref IS
  'Cross-reference cache for /api/v2/legislative/eur-lex/laws/{celex}/xref. Lazily written per CELEX; safe to truncate (rebuilds on demand).';

ALTER TABLE public.law_xref ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS law_xref_public_read ON public.law_xref;
CREATE POLICY law_xref_public_read ON public.law_xref
    FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS law_xref_service_all ON public.law_xref;
CREATE POLICY law_xref_service_all ON public.law_xref
    FOR ALL TO service_role USING (true) WITH CHECK (true);

GRANT SELECT ON public.law_xref TO anon, authenticated;
GRANT ALL    ON public.law_xref TO service_role;
