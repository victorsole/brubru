-- 255: an id the news API has served keeps resolving, and a story does not change
-- kind when the store that serves it changes (29 Sep 2026).
--
-- /api/v2/news unions two stores and dedups them by normalised URL, with
-- economy_items winning. Identity was therefore decided at READ time by whichever
-- store happened to hold the row. An institutional story ingested first is served
-- under its UUID; when an agency twin arrives later the UUID is suppressed and the
-- story comes back under an integer id, sometimes under a different kind.
--
-- Measured before this migration:
--   1,815  institutional stories currently hidden by a twin
--   1,599  of them existed BEFORE that twin, so we served them
--   1,113  were visible for more than a DAY (the longest, 99.2 days)
--      200  of those also changed kind on the way
-- Four of those ids were called on production and every one returned 404. A client
-- that stored one reads it as a deletion. It is the same defect GovClipping reported
-- for `kind`, one level down: an identifier decided by which row happens to answer.
--
-- The fix is additive on purpose. Changing which store wins would have re-pointed
-- 1,599 ids in the opposite direction, which is the same harm again, on the clients
-- who are already following the CURRENT ids. So the served ids do not move: an
-- alias keeps every id we ever handed out resolving to whatever serves that story
-- now, and the kind a story is served under is carried across the handover.

-- news_url_key() strips the query string, and some EU sites carry the article's
-- identity there: chips-ju.europa.eu/NewsDetails?id=... collapses TEN distinct
-- articles onto one key. That makes the key a prefilter, not an identity, so the
-- dedup suppressed institutional rows that were not twins, and "the canonical id for
-- this story" had no single answer. Only 2 suppressions in the whole corpus actually
-- depend on the query being stripped, so exactness costs nothing.
--
-- Keeping the WHOLE query was wrong the other way: EIGE publishes the same article
-- with ?language_content_entity=en, and 2,107 URLs carry utm_source/medium/campaign.
-- So the rule is measured, not guessed: drop the parameters that demonstrably do not
-- identify (utm_*, language_content_entity, pk_*, PM_from) and keep the rest, which
-- leaves ?id= and ?filename= (341 document downloads) doing their job. Anything not
-- classified is KEPT: over-serving one duplicate is recoverable, hiding a real
-- article behind a 404 is what this migration exists to stop.
--
-- The lossy key is KEPT as the indexed prefilter (migration 252 and the v3 index
-- below are partial on it, and redefining it would rebuild both); exactness is an
-- extra predicate on top.
CREATE OR REPLACE FUNCTION news_url_key_exact(url text)
RETURNS text
LANGUAGE sql IMMUTABLE AS $fn$
    WITH u AS (
        -- replace(&amp;) first: two scrapers stored the HTML entity instead of '&',
        -- which split the query wrongly and made one article look like two.
        SELECT rtrim(lower(btrim(split_part(replace(url, '&amp;', '&'), '#', 1))), '/') AS whole
    ), parts AS (
        SELECT regexp_replace(split_part(whole, '?', 1), '^https?://(www\.)?', '') AS base,
               nullif(split_part(whole, '?', 2), '') AS qs
          FROM u
    ), kept AS (
        SELECT p.base, string_agg(kv, '&' ORDER BY kv) AS q
          FROM parts p
          CROSS JOIN LATERAL unnest(string_to_array(coalesce(p.qs, ''), '&')) AS kv
         WHERE kv <> ''
           -- The three tracking families actually present in the corpus, by prefix:
           -- utm_* (2,107 URLs), pk_* and pm_* (Matomo / newsroom windows), plus the
           -- language variant. Everything else is KEPT, including ?id= and ?filename=.
           AND split_part(kv, '=', 1) <> 'language_content_entity'
           AND split_part(kv, '=', 1) NOT LIKE 'utm\_%'
           AND split_part(kv, '=', 1) NOT LIKE 'pk\_%'
           AND split_part(kv, '=', 1) NOT LIKE 'pm\_%'
         GROUP BY p.base
    )
    SELECT coalesce((SELECT base || '?' || q FROM kept), (SELECT base FROM parts))
$fn$;


CREATE TABLE IF NOT EXISTS news_id_alias (
    alias_id      TEXT PRIMARY KEY,
    canonical_id  TEXT NOT NULL,
    url_key       TEXT,
    first_seen    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE news_id_alias IS
    'An id /api/v2/news once served, and the id that serves the same story now. Read '
    'by the item route when a requested id no longer resolves on its own.';

ALTER TABLE news_id_alias ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS news_id_alias_read ON news_id_alias;
CREATE POLICY news_id_alias_read ON news_id_alias FOR SELECT USING (true);
DROP POLICY IF EXISTS news_id_alias_service ON news_id_alias;
CREATE POLICY news_id_alias_service ON news_id_alias FOR ALL USING (true) WITH CHECK (true);

GRANT SELECT ON news_id_alias TO anon, authenticated;
GRANT ALL ON news_id_alias TO service_role;

CREATE INDEX IF NOT EXISTS ix_news_id_alias_canonical ON news_id_alias (canonical_id);


-- The dedup predicate and the serving predicate must select the SAME rows. The list
-- now filters the agency half on news_kind, so the dedup does too, and it needs its
-- own partial index: ix_economy_items_news_url_key_v2 is partial on the item_type
-- list and the planner cannot prove a match against a different predicate.
CREATE INDEX IF NOT EXISTS ix_economy_items_news_url_key_v3
    ON economy_items (public.news_url_key(public_url))
    WHERE news_kind IS NOT NULL;


-- Carry the kind across the handover -- FORWARD ONLY.
--
-- The first cut of this migration restored the first-served kind on the 200 stories
-- where the two stores disagreed. That is defensible in theory and wrong in practice:
-- those stories are being served under the agency kind TODAY, so "restoring" them
-- moves 200 items between kinds on the day we promised a client that nothing would
-- move again, and hands their search index 200 duplicate documents. The older kind is
-- not more correct; it is only older.
--
-- So nothing moves now. Instead the handover stops moving anything from here on: when
-- an agency row arrives for a story an institutional row is already serving, it adopts
-- the kind that story is already published under.
CREATE OR REPLACE FUNCTION brubru_carry_news_kind()
RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    held text;
BEGIN
    IF NEW.news_kind IS NULL THEN
        RETURN NEW;
    END IF;
    SELECT n.news_kind INTO held
      FROM eu_news_items n
     WHERE n.news_kind IS NOT NULL
       AND public.news_url_key(n.source_url) = public.news_url_key(NEW.public_url)
       AND public.news_url_key_exact(n.source_url) = public.news_url_key_exact(NEW.public_url)
     ORDER BY n.created_at
     LIMIT 1;
    IF held IS NOT NULL AND held <> NEW.news_kind THEN
        NEW.news_kind := held;
    END IF;
    RETURN NEW;
END;
$$;

-- THE NAME IS LOAD-BEARING. PostgreSQL fires BEFORE triggers in alphabetical order by
-- trigger name, so this has to sort AFTER trg_economy_items_pin_kind: named
-- ..._carry_kind it ran first, saw news_kind still NULL, returned early, and the carry
-- silently never happened. "then_carry" sorts after "pin". Do not rename it to
-- something tidier without checking the order it lands in.
DROP TRIGGER IF EXISTS trg_economy_items_carry_kind ON economy_items;
DROP TRIGGER IF EXISTS trg_economy_items_then_carry_kind ON economy_items;
CREATE TRIGGER trg_economy_items_then_carry_kind
    BEFORE INSERT ON economy_items
    FOR EACH ROW EXECUTE FUNCTION brubru_carry_news_kind();


-- Keep recording them. The backfill below is a one-off, and twins keep arriving: a
-- verification run 40 minutes after the first backfill already found institutional ids
-- newly hidden with no alias. An invariant that only holds at migration time is not an
-- invariant, so the alias is written when the handover happens.
CREATE OR REPLACE FUNCTION brubru_record_news_alias()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.news_kind IS NULL THEN
        RETURN NULL;
    END IF;
    INSERT INTO news_id_alias (alias_id, canonical_id, url_key)
    SELECT n.id::text, NEW.id::text, public.news_url_key(n.source_url)
      FROM eu_news_items n
     WHERE n.news_kind IS NOT NULL
       AND public.news_url_key(n.source_url) = public.news_url_key(NEW.public_url)
       AND public.news_url_key_exact(n.source_url) = public.news_url_key_exact(NEW.public_url)
    ON CONFLICT (alias_id) DO UPDATE
       SET canonical_id = EXCLUDED.canonical_id, last_updated = NOW();
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_economy_items_record_alias ON economy_items;
CREATE TRIGGER trg_economy_items_record_alias
    AFTER INSERT ON economy_items
    FOR EACH ROW EXECUTE FUNCTION brubru_record_news_alias();


-- Record every id we have served that a twin now hides.
-- DISTINCT ON: two agency rows can hold the exact same URL (AMLA publishes some
-- documents twice), and an alias must name ONE id. The lowest id is the one that
-- has been served longest, so it is the one a client is most likely to already hold.
INSERT INTO news_id_alias (alias_id, canonical_id, url_key)
SELECT DISTINCT ON (n.id) n.id::text, e.id::text, public.news_url_key(n.source_url)
  FROM eu_news_items n
  JOIN economy_items e
    ON public.news_url_key(e.public_url) = public.news_url_key(n.source_url)
   AND news_url_key_exact(e.public_url) = news_url_key_exact(n.source_url)
   AND e.news_kind IS NOT NULL
 WHERE n.news_kind IS NOT NULL
   AND n.created_at < e.creation_date
 ORDER BY n.id, e.id
ON CONFLICT (alias_id) DO UPDATE
   SET canonical_id = EXCLUDED.canonical_id,
       last_updated = NOW();
