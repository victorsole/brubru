-- 306: a real change signal on seven funding tables, so their endpoints can serve updated_date (20 Oct 2026).
--
-- Read on /api/v2/funding: 22 endpoints (cohesion finances and outcomes for 8 funds, EAFRD, EAGF,
-- the Solidarity Fund, F&T funded projects, funding opportunities, programmes) returned
-- updated_date null on every item, so a partner could not sync them incrementally. Each table has
-- an updated_at or last_updated column, but its writers stamp it on every run, so serving it would
-- have reported every row as changed every night. brubru_touch_if_changed (the trigger already on
-- tenders, secondary_acts and eu_laws) keeps OLD's value unless another column really changed,
-- and logs the changed column names in brubru_change_log.
--
-- Arguments: the signal column; the bookkeeping columns a re-read rewrites (ignored); the
-- columns an UPDATE must never move (anchors). No row is rewritten here.

SET LOCAL lock_timeout = '10s';

DROP TRIGGER IF EXISTS trg_eu_cohesion_finances_touch ON eu_cohesion_finances;
CREATE TRIGGER trg_eu_cohesion_finances_touch BEFORE UPDATE ON eu_cohesion_finances
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', 'fetched_at', 'created_at');

DROP TRIGGER IF EXISTS trg_eu_cohesion_outcomes_touch ON eu_cohesion_outcomes;
CREATE TRIGGER trg_eu_cohesion_outcomes_touch BEFORE UPDATE ON eu_cohesion_outcomes
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', 'fetched_at', 'created_at');

DROP TRIGGER IF EXISTS trg_eu_cap_payments_touch ON eu_cap_payments;
CREATE TRIGGER trg_eu_cap_payments_touch BEFORE UPDATE ON eu_cap_payments
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', 'fetched_at', 'created_at');

DROP TRIGGER IF EXISTS trg_eu_solidarity_fund_touch ON eu_solidarity_fund;
CREATE TRIGGER trg_eu_solidarity_fund_touch BEFORE UPDATE ON eu_solidarity_fund
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('updated_at', 'fetched_at', 'created_at');

DROP TRIGGER IF EXISTS trg_ft_funded_projects_touch ON ft_funded_projects;
CREATE TRIGGER trg_ft_funded_projects_touch BEFORE UPDATE ON ft_funded_projects
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', '');

DROP TRIGGER IF EXISTS trg_funding_opportunities_touch ON funding_opportunities;
CREATE TRIGGER trg_funding_opportunities_touch BEFORE UPDATE ON funding_opportunities
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', 'scraped_at', '');

DROP TRIGGER IF EXISTS trg_ft_programmes_touch ON ft_programmes;
CREATE TRIGGER trg_ft_programmes_touch BEFORE UPDATE ON ft_programmes
    FOR EACH ROW EXECUTE FUNCTION brubru_touch_if_changed('last_updated', '', 'created_at');
