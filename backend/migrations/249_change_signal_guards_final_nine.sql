-- 249: the last nine tables behind a ?updated_from= filter.
--
-- Completes the sweep started in 245-248. Every model named in an
-- `X >= updated_from` filter under api/ was resolved to its table; these nine had no
-- guard at all, so their change signal was correct only for as long as every writer
-- remembered to move it and never moved it for nothing.
--
-- Arguments: signal columns | ignored but left moving | creation anchors pinned.
-- A "when we last looked" column (scraped_at, body_fetched_at, last_synced_at) is
-- ignored rather than compared: a pass that fetches the same body again is not a
-- change, while the body column itself is compared and will catch a real one.

DROP TRIGGER IF EXISTS trg_committee_work_items_touch ON committee_work_items;
CREATE TRIGGER trg_committee_work_items_touch BEFORE UPDATE ON committee_work_items
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen');

DROP TRIGGER IF EXISTS trg_ep_votes_touch ON ep_votes;
CREATE TRIGGER trg_ep_votes_touch BEFORE UPDATE ON ep_votes
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', '', 'created_at');

DROP TRIGGER IF EXISTS trg_eu_officials_touch ON eu_officials;
CREATE TRIGGER trg_eu_officials_touch BEFORE UPDATE ON eu_officials
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen');

DROP TRIGGER IF EXISTS trg_rsb_opinions_touch ON rsb_opinions;
CREATE TRIGGER trg_rsb_opinions_touch BEFORE UPDATE ON rsb_opinions
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen');

DROP TRIGGER IF EXISTS trg_secondary_acts_touch ON secondary_acts;
CREATE TRIGGER trg_secondary_acts_touch BEFORE UPDATE ON secondary_acts
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at,body_fetched_at', 'first_seen');

DROP TRIGGER IF EXISTS trg_tenders_touch ON tenders;
CREATE TRIGGER trg_tenders_touch BEFORE UPDATE ON tenders
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', 'last_synced_at', 'created_at');

DROP TRIGGER IF EXISTS trg_transparency_meetings_touch ON transparency_meetings;
CREATE TRIGGER trg_transparency_meetings_touch BEFORE UPDATE ON transparency_meetings
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen');

DROP TRIGGER IF EXISTS trg_tris_notifications_touch ON tris_notifications;
CREATE TRIGGER trg_tris_notifications_touch BEFORE UPDATE ON tris_notifications
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', 'first_seen');

-- amendment_documents: same wrong column as mep_amendments had. /parliament/amendment-
-- documents filtered ?updated_from= on scraped_at, so a re-scrape finding nothing new
-- would still report every row. updated_at is populated on all 1,356 rows; the endpoint
-- moves to it (api/v1/ep_entities.py).
DROP TRIGGER IF EXISTS trg_amendment_documents_touch ON amendment_documents;
CREATE TRIGGER trg_amendment_documents_touch BEFORE UPDATE ON amendment_documents
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', 'scraped_at,body_fetched_at', '');
