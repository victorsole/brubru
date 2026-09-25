-- EESC and CoR opinions fetched their full text and could not store it (25 Sep 2026).
--
-- `body_source` is VARCHAR(8). The backfill writes 'fetched:html' or 'fetched:pdf', so
-- every UPDATE failed with StringDataRightTruncation and both corpora "finished" in
-- seconds having written nothing, after downloading the opinions in full: the first EESC
-- row had 25,205 characters of text and 52,010 of HTML in hand when the write was
-- refused.
--
-- The same shape as migration 240 a day earlier, where a 63-character group name met a
-- VARCHAR(20) and emptied five EP tables. A width chosen for the values a column happens
-- to hold today is a trap for the next writer: body_source is a label, so it gets label
-- width, and the values it records ('fetched:html', 'fetched:pdf', 'composed:title') stay
-- readable rather than being abbreviated to fit.
ALTER TABLE eu_eesc_opinions ALTER COLUMN body_source TYPE VARCHAR(40);
ALTER TABLE eu_cor_opinions  ALTER COLUMN body_source TYPE VARCHAR(40);

COMMENT ON COLUMN eu_eesc_opinions.body_source IS
    'How the body was obtained: fetched:html, fetched:pdf, or a composed:* form. '
    'Widened from VARCHAR(8) on 25 Sep 2026, which was too short for its own values.';
COMMENT ON COLUMN eu_cor_opinions.body_source IS
    'How the body was obtained: fetched:html, fetched:pdf, or a composed:* form. '
    'Widened from VARCHAR(8) on 25 Sep 2026, which was too short for its own values.';
