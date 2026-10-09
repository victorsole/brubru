-- 289: oeil_procedures carries the procedure page itself (body_txt / body_html), 9 Oct 2026.
--
-- /resolution-procedures serves the OEIL procedure page as the body of a procedure Parliament
-- adopted no text for. It read that page from legislative_carriages, which holds no row for
-- 429 of the 957 procedures (debates such as 2026/2561(RSP), 9th-term resolutions), so those
-- were served a 150-character summary of our own columns. The page is the same one
-- scripts/sync_oeil_procedures.py already reads to fill this table; it now keeps it, cleaned
-- by services/scrapers/oeil_body_scraper.parse_body exactly like the carriage copy.
ALTER TABLE public.oeil_procedures
    ADD COLUMN IF NOT EXISTS body_txt  TEXT,
    ADD COLUMN IF NOT EXISTS body_html TEXT;

COMMENT ON COLUMN public.oeil_procedures.body_txt IS
    'The OEIL procedure page as text (parse_body, as legislative_carriages.oeil_text_body). NULL until the page is read by sync_oeil_procedures.py.';
