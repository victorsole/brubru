-- 248: the change signal is maintained by the table, not by each writer's goodwill.
--
-- Nine more tables back an endpoint that answers ?updated_from=, and on all nine the
-- filtered column moved only when a writer remembered to move it. That is the same
-- arrangement that failed on ep_resolutions, where four scheduled writers touch the
-- table and guarding one of them left another stamping all 351 rows every run. It
-- fails in both directions: a writer that stamps without changing anything makes a
-- partner re-pull the corpus, and a writer that changes a row without stamping hides
-- the change from them completely, which is the worse of the two.
--
-- brubru_touch_if_changed (migration 246) decides once, where every write passes.
--
-- Arguments: signal columns | columns ignored but left moving | creation anchors pinned.
-- An ingestion anchor (scraped_at) is ignored, never pinned: it must keep moving every
-- run because it is what answers "is this feed still alive". The "when we last looked"
-- columns on legislative_carriages are ignored for the same reason -- an enrichment pass
-- that finds nothing new should not read as a change.

DROP TRIGGER IF EXISTS trg_eu_calendar_events_touch ON eu_calendar_events;
CREATE TRIGGER trg_eu_calendar_events_touch BEFORE UPDATE ON eu_calendar_events
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen');

DROP TRIGGER IF EXISTS trg_catalan_translations_touch ON catalan_translations;
CREATE TRIGGER trg_catalan_translations_touch BEFORE UPDATE ON catalan_translations
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', '', 'created_at');

DROP TRIGGER IF EXISTS trg_commission_documents_touch ON commission_documents;
CREATE TRIGGER trg_commission_documents_touch BEFORE UPDATE ON commission_documents
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen');

DROP TRIGGER IF EXISTS trg_eprs_publications_touch ON eprs_publications;
CREATE TRIGGER trg_eprs_publications_touch BEFORE UPDATE ON eprs_publications
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen');

DROP TRIGGER IF EXISTS trg_legislative_carriages_touch ON legislative_carriages;
CREATE TRIGGER trg_legislative_carriages_touch BEFORE UPDATE ON legislative_carriages
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed(
        'last_updated',
        'scraped_at,enriched_at,oeil_body_fetched_at,legislative_train_updated_at,oeil_roles_parsed_at',
        'first_seen');

DROP TRIGGER IF EXISTS trg_texts_adopted_touch ON texts_adopted;
CREATE TRIGGER trg_texts_adopted_touch BEFORE UPDATE ON texts_adopted
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen');

DROP TRIGGER IF EXISTS trg_parl_questions_touch ON parliamentary_questions;
CREATE TRIGGER trg_parl_questions_touch BEFORE UPDATE ON parliamentary_questions
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen');

DROP TRIGGER IF EXISTS trg_committee_transcripts_touch ON committee_meeting_transcripts;
CREATE TRIGGER trg_committee_transcripts_touch BEFORE UPDATE ON committee_meeting_transcripts
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', '', 'first_seen');

-- mep_amendments carries both. /parliament/amendments filtered ?updated_from= on
-- scraped_at, which answers "when did we last look at it", not "when did it change";
-- every re-scrape would have reported the whole corpus. updated_at is populated on all
-- 58,399 rows, so the endpoint moves to it (api/v1/ep_entities.py) and the trigger
-- keeps it honest.
DROP TRIGGER IF EXISTS trg_mep_amendments_touch ON mep_amendments;
CREATE TRIGGER trg_mep_amendments_touch BEFORE UPDATE ON mep_amendments
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', 'scraped_at', '');
