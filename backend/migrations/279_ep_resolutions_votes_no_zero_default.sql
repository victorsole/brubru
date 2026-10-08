-- 279: an uncounted vote is NULL, never 0.
--
-- ep_resolutions.vote_for / vote_against / vote_abstention / vote_total defaulted to 0,
-- so every row inserted without a tally said "0 for, 0 against, 0 abstentions": 72 rows
-- on 8 Oct 2026, 35 of them resolutions that were never voted at all. The values
-- themselves are corrected by scripts/enrich_ep_texts_and_resolutions.py (the final
-- plenary vote, else NULL); this stops new rows from inventing them again.
ALTER TABLE ep_resolutions ALTER COLUMN vote_for        DROP DEFAULT;
ALTER TABLE ep_resolutions ALTER COLUMN vote_against    DROP DEFAULT;
ALTER TABLE ep_resolutions ALTER COLUMN vote_abstention DROP DEFAULT;
ALTER TABLE ep_resolutions ALTER COLUMN vote_total      DROP DEFAULT;
