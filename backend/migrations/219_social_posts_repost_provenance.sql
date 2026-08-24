-- 219: repost provenance on social_posts + account-identity hygiene
--
-- WHY (audit, 24 August 2026)
--
-- `social_posts` carried `repost_count` (a metric) but nothing recording whether
-- the row IS a repost. A repost was therefore indistinguishable from an original
-- statement by the account that carried it. 398 distinct post bodies appeared
-- under more than one account in 30 days. Some are legitimate coordinated
-- campaigns; others are misattribution, and one of them was:
--
--     "Je suis candidat a l'election presidentielle"
--        -> stored under Raphael Glucksmann AND Thomas Pellerin-Carlin
--
-- Read literally, the database says Pellerin-Carlin declared for the French
-- presidency. He reposted Glucksmann. MEUB > MEP Watch and Position Analysis are
-- both slated to cite social_posts as evidence of what an actor said, which
-- would turn that into a fabricated position -- the same failure class as the
-- August fabrication audit, in a dataset we are about to surface.
--
-- Also: 171 MEPs were stored under more than one name spelling across 786
-- account rows ("Matthias Ecke" / "Matthias ECKE"), because the EP writes
-- surnames in caps and Wikidata uses title case. MEP Watch would show one
-- person as two. And 11 account_urls existed twice despite the loaders being
-- documented as idempotent upserts on that column.

-- 1. Repost provenance -------------------------------------------------------
ALTER TABLE social_posts
  ADD COLUMN IF NOT EXISTS is_repost BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS original_author TEXT;

COMMENT ON COLUMN social_posts.is_repost IS
  'TRUE when this account amplified someone else''s post rather than authoring it. '
  'Never cite a row with is_repost = TRUE as evidence of what this actor said.';
COMMENT ON COLUMN social_posts.original_author IS
  'Handle of the author when is_repost is TRUE; NULL otherwise.';

-- Backfill what is recoverable from the stored text. X syndication prefixes a
-- repost with "RT @handle:", so those rows can be classified retrospectively.
-- Bluesky reposts carry no marker in `content` and will be classified going
-- forward by the fetcher, not here: inventing a value for them would be worse
-- than leaving them FALSE, so they stay FALSE and unclaimed.
UPDATE social_posts
   SET is_repost = TRUE,
       original_author = substring(content from '^RT @([A-Za-z0-9_]{1,15})\s*:')
 WHERE content ~ '^RT @[A-Za-z0-9_]{1,15}\s*:'
   AND is_repost = FALSE;

CREATE INDEX IF NOT EXISTS idx_social_posts_is_repost
  ON social_posts (is_repost) WHERE is_repost = TRUE;

-- 2. Account identity --------------------------------------------------------
-- Normalise the name split BEFORE adding the constraint, so the constraint has
-- something consistent to protect. Prefer the title-case spelling: it is what a
-- reader expects to see in MEP Watch, and the all-caps form is an EP artefact.
WITH canon AS (
  SELECT lower(entity_name) AS k,
         (array_agg(entity_name ORDER BY (entity_name = upper(entity_name)), entity_name))[1] AS best
    FROM social_accounts
   WHERE entity_type = 'mep'
   GROUP BY lower(entity_name)
  HAVING count(DISTINCT entity_name) > 1
)
UPDATE social_accounts a
   SET entity_name = c.best
  FROM canon c
 WHERE lower(a.entity_name) = c.k
   AND a.entity_name <> c.best;

-- Repoint posts off duplicate account rows, then drop the emptied duplicates.
-- Posts move first: deleting an account row that still owns posts would either
-- cascade them away or orphan them, and both lose evidence.
WITH ranked AS (
  SELECT id, lower(account_url) AS k,
         row_number() OVER (PARTITION BY lower(account_url) ORDER BY created_at, id) AS rn,
         first_value(id) OVER (PARTITION BY lower(account_url) ORDER BY created_at, id) AS keep_id
    FROM social_accounts
)
UPDATE social_posts p
   SET account_id = r.keep_id
  FROM ranked r
 WHERE p.account_id = r.id AND r.rn > 1
   AND NOT EXISTS (
     SELECT 1 FROM social_posts q
      WHERE q.account_id = r.keep_id AND q.platform_post_id = p.platform_post_id);

DELETE FROM social_posts p
 USING (SELECT id, row_number() OVER (PARTITION BY lower(account_url)
                                      ORDER BY created_at, id) AS rn
          FROM social_accounts) r
 WHERE p.account_id = r.id AND r.rn > 1;

DELETE FROM social_accounts a
 USING (SELECT id, row_number() OVER (PARTITION BY lower(account_url)
                                      ORDER BY created_at, id) AS rn
          FROM social_accounts) r
 WHERE a.id = r.id AND r.rn > 1;

-- Now the loaders' documented idempotency is enforced rather than assumed.
CREATE UNIQUE INDEX IF NOT EXISTS uq_social_accounts_account_url_lower
  ON social_accounts (lower(account_url));
