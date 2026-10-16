-- 304: restate the final change-signal trigger of eu_laws, so the migrations replay in number order.
--
-- Post-deploy audit, 16 Oct 2026: the API session's 297 (ignore eurovoc_fetched_at and body_fetched_at on eu_laws,
-- write brubru_change_log) was applied after 299-303 although it sorts before them. Replayed in number order, 299
-- re-creates update_eu_laws_updated_at without 297's two ignored columns (a job that only re-stamps a fetch would
-- move updated_at again) and 301/302 replace the function without the change log; 303 (its guard now accepts 302's
-- text) restores the function, and this file restores the trigger. In production (where both are already right) it
-- only re-creates the trigger as it is.

SET LOCAL lock_timeout = '10s';

DO $check$
BEGIN
    IF md5(pg_get_functiondef('brubru_touch_if_changed'::regproc)) <> 'ee2bee11c6ed961dcc88d14f8dfa8bb8' THEN
        RAISE EXCEPTION 'brubru_touch_if_changed is not the text of 303: apply 303 first, or rebuild 304 from the live text';
    END IF;
END
$check$;

DROP TRIGGER IF EXISTS update_eu_laws_updated_at ON eu_laws;
CREATE TRIGGER update_eu_laws_updated_at
    BEFORE UPDATE ON eu_laws
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', 'celex_year,celex_type,celex_number,eurovoc_fetched_at,body_fetched_at', 'created_at');
