-- Migration 132: read-only convenience view UNIONing the five funding
-- sources behind the Tenderator unified-feed into one shape.
--
-- This is a cleanup / option, NOT a runtime requirement. The endpoint can
-- still query each table directly via its ORM — this view is intended as a
-- single SQL anchor for dashboard-stats, analytics, and future ad-hoc
-- queries ("how many funding items did Brubru watch on date X?").
--
-- Sources:
--   1. tenders                  (TED public procurement)               id integer
--   2. ft_calls_for_proposals   (F&T grants)                            id uuid
--   3. ft_calls_for_tenders     (F&T public procurement)                id uuid
--   4. ft_funded_projects       (CORDIS-like)                           id uuid
--   5. economy_items            (decentralised agency procurement)      id integer
--
-- All ids are cast to TEXT and prefixed with the source tag so the union is
-- type-uniform and the resulting `id` matches the format the Tenderator
-- already returns in /unified-feed responses.

CREATE OR REPLACE VIEW v_funding_unified AS
-- TED tenders
SELECT
    'ted'::text                      AS source,
    'ted:' || t.id::text             AS id,
    t.publication_number             AS external_id,
    t.title                          AS title,
    t.description                    AS summary,
    t.status                         AS status,
    t.submission_deadline            AS deadline,
    t.estimated_value::numeric       AS budget,
    COALESCE(t.estimated_value_currency, 'EUR') AS currency,
    t.ted_url                        AS source_url,
    t.official_name                  AS organisation,
    t.buyer_country                  AS country,
    NULL::text                       AS programme,
    t.publication_date               AS published_at,
    NULL::text                       AS body_code
FROM tenders t

UNION ALL

-- F&T calls for proposals (grants)
SELECT
    'ft_proposals'::text             AS source,
    'ft_proposals:' || p.id::text    AS id,
    p.topic_id                       AS external_id,
    p.title                          AS title,
    p.description                    AS summary,
    p.status                         AS status,
    p.deadline AT TIME ZONE 'UTC'    AS deadline,
    p.indicative_budget              AS budget,
    COALESCE(p.budget_currency, 'EUR') AS currency,
    p.source_url                     AS source_url,
    NULL::text                       AS organisation,
    NULL::text                       AS country,
    p.framework_programme            AS programme,
    p.published_at AT TIME ZONE 'UTC' AS published_at,
    NULL::text                       AS body_code
FROM ft_calls_for_proposals p
WHERE p.is_test IS NOT TRUE

UNION ALL

-- F&T calls for tenders (procurement on the F&T portal)
SELECT
    'ft_tenders'::text               AS source,
    'ft_tenders:' || tt.id::text     AS id,
    tt.tender_reference              AS external_id,
    tt.title                         AS title,
    tt.description                   AS summary,
    tt.status                        AS status,
    tt.deadline AT TIME ZONE 'UTC'   AS deadline,
    tt.estimated_value               AS budget,
    COALESCE(tt.value_currency, 'EUR') AS currency,
    tt.source_url                    AS source_url,
    tt.contracting_authority         AS organisation,
    NULL::text                       AS country,
    NULL::text                       AS programme,
    tt.published_at AT TIME ZONE 'UTC' AS published_at,
    NULL::text                       AS body_code
FROM ft_calls_for_tenders tt
WHERE tt.is_test IS NOT TRUE

UNION ALL

-- F&T funded projects (CORDIS-like)
SELECT
    'ft_projects'::text              AS source,
    'ft_projects:' || fp.id::text    AS id,
    fp.project_id                    AS external_id,
    fp.title                         AS title,
    fp.objective                     AS summary,
    fp.status                        AS status,
    fp.end_date::timestamptz         AS deadline,
    COALESCE(fp.eu_contribution, fp.total_cost) AS budget,
    COALESCE(fp.cost_currency, 'EUR') AS currency,
    fp.source_url                    AS source_url,
    fp.coordinator_name              AS organisation,
    fp.coordinator_country::text     AS country,
    fp.framework_programme           AS programme,
    fp.start_date::timestamptz       AS published_at,
    NULL::text                       AS body_code
FROM ft_funded_projects fp
WHERE fp.is_test IS NOT TRUE

UNION ALL

-- Decentralised EU agency procurement (the data the public
-- /api/v2/funding/{agency}-* endpoints serve).
SELECT
    'agency'::text                                   AS source,
    'agency:' || ei.id::text                         AS id,
    ei.body_code                                     AS external_id,
    ei.title                                         AS title,
    ei.summary                                       AS summary,
    NULL::text                                       AS status,
    ei.document_date                                 AS deadline,
    NULL::numeric                                    AS budget,
    'EUR'::text                                      AS currency,
    ei.public_url                                    AS source_url,
    ei.body_code                                     AS organisation,
    NULL::text                                       AS country,
    upper(ei.item_type)                              AS programme,
    ei.creation_date                                 AS published_at,
    ei.body_code                                     AS body_code
FROM economy_items ei
WHERE ei.item_type IN ('tender', 'grant', 'eoi_call', 'startup_funding');

-- View defaults to invoker-rights; grant SELECT to the same roles as the
-- underlying base tables so PostgREST / the Supabase Data API can read it.
GRANT SELECT ON v_funding_unified TO anon, authenticated;
GRANT SELECT ON v_funding_unified TO service_role;

COMMENT ON VIEW v_funding_unified IS
'Read-only UNION of the 5 funding sources behind the Tenderator unified-feed: TED + F&T proposals + F&T tenders + F&T funded projects + decentralised EU agency procurement. id is prefixed with the source tag so the same format as /api/tenders/unified-feed responses is preserved.';
