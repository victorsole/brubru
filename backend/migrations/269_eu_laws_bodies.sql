-- 269: store the full text of each law so /laws can serve it.
--
-- GovClipping walks /api/v2/legislative/eur-lex/laws and found body_txt and
-- body_html null on all 17,947 rows of their backfill window. That was by design:
-- the list said "call /laws/{celex}/text for the body", and that route fetches the
-- document live from Cellar on every call. Fine for one act, impossible for a list
-- -- a 100-row page would be 100 live Cellar fetches.
--
-- Victor's instruction on 1 October 2026 is that the list must serve body_txt and
-- body_html exactly as the text route does, so the text has to be stored rather than
-- fetched per request. This is also the partner's own stated preference: scripts go
-- to the official source, extract, and store.
--
-- Size: sampled from Cellar, a law averages 41 KB of XHTML (median 29 KB), so the
-- two columns add roughly 2.3 GB to a 182 MB table. body_chars exists so coverage can
-- be judged on the LENGTH distribution rather than on non-null, because a short body
-- is how a bot challenge or a nav fragment gets stored and still reads as "filled".
ALTER TABLE eu_laws
    ADD COLUMN IF NOT EXISTS body_html        text,
    ADD COLUMN IF NOT EXISTS body_txt         text,
    ADD COLUMN IF NOT EXISTS body_chars       integer,
    ADD COLUMN IF NOT EXISTS body_fetched_at  timestamptz;

COMMENT ON COLUMN eu_laws.body_html IS 'XHTML of the act as Cellar serves it.';
COMMENT ON COLUMN eu_laws.body_txt IS 'Plain text stripped from body_html.';
COMMENT ON COLUMN eu_laws.body_chars IS 'Length of body_txt. Judge coverage on this distribution, never on non-null.';
COMMENT ON COLUMN eu_laws.body_fetched_at IS 'When the body was last read from Cellar. Drives the resumable drain.';

-- The drain takes unfetched rows first, then the stalest.
CREATE INDEX IF NOT EXISTS idx_eu_laws_body_fetched
    ON eu_laws (body_fetched_at NULLS FIRST)
    WHERE celex IS NOT NULL AND celex <> '';
