-- 273: index at most 200,000 characters of a body; store the body whole.
--
-- A tsvector cannot exceed 1 MB. EBA reporting packages read from their zips run to
-- 1.6 MB of text, and the BEFORE trigger then aborted the whole write batch
-- ("string is too long for tsvector", 5 Oct 2026). The body column keeps every
-- character; only the search index reads the first 200,000.
CREATE OR REPLACE FUNCTION public.economy_items_tsv_update()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    NEW.search_vector := to_tsvector('english',
        coalesce(NEW.title, '') || ' ' || coalesce(NEW.summary, '') || ' '
        || left(coalesce(NEW.body_txt, ''), 200000));
    RETURN NEW;
END $function$;
