"""A site that will not serve us is degraded for 72 hours after the job's last good run, then fails.

30 Oct 2026 (Victor's decision): epthinktank.eu, the EPRS blog and its "EU legislation in
progress" page, stopped answering on 29 Oct (a timeout from one machine, a refused connection
from another, a 1,290-byte refusal on Railway). The two EPRS jobs failed at every warm run and,
failing twice in a row, made the cron red twice a day. A refusal (a timeout, a refused
connection, a WAF page, an HTTP error status) is now recorded `degraded` with its reason while
the job's last success is under 72 hours old, and fails after. A page that answers but does not
parse is never a refusal: it fails at once, as before.

2 Nov 2026: the red after 72 hours brought out that the blog had not stopped answering but ended
(EPRS's post of 27 Oct, stored in our own table, said so). The feed and the job on its legislation
page are retired; the same rule now covers the other outages that reddened the cron that week: the
WTO notifications site, ECHA among the bespoke news sources, Cellar for the three eu_laws jobs."""
import asyncio
import importlib.util
import pathlib
from datetime import datetime, timedelta, timezone

from services.scrapers import eprs_sync_service as svc
from services.sync import freshness

BACKEND = pathlib.Path(__file__).resolve().parents[1]
START, END = datetime(2026, 10, 27), datetime(2026, 10, 30)


def _script():
    spec = importlib.util.spec_from_file_location("sync_eprs_publications_refusals", BACKEND / "scripts" / "sync_eprs_publications.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_grace_runs_72_hours_from_the_last_good_run(capsys):
    now = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
    assert freshness.unreachable_exit(["HTTP 404"], now - timedelta(hours=71), now) == 0
    assert "[SYNC_STATUS] degraded: source unreachable (HTTP 404)" in capsys.readouterr().out
    assert freshness.unreachable_exit(["HTTP 404"], now - timedelta(hours=73), now) == 1
    assert freshness.unreachable_exit(["HTTP 404"], None, now) == 1           # never good: fails
    naive = (now - timedelta(hours=9)).replace(tzinfo=None)                   # a stored naive stamp is UTC
    assert freshness.unreachable_exit(["timeout"], naive, now) == 0


def test_a_portal_refusal_is_marked_and_an_unparseable_page_is_not():
    async def not_found(url, params=None):
        return 404, "x" * 1290

    async def refused(url, params=None):
        raise ConnectionRefusedError("connect ECONNREFUSED")

    async def garbage(url, params=None):
        return 200, "<html>not a feed</html>"

    def fetch_rss(http_get):
        report = svc.SourceReport(name="thinktank_portal")
        items = asyncio.run(svc.ThinkTankPortalSource(http_get=http_get)._fetch_rss(START, END, report))
        return items, report

    for http_get in (not_found, refused):
        items, report = fetch_rss(http_get)
        assert items is None and report.refused == report.errors and report.errors
    items, report = fetch_rss(garbage)
    assert items is None and report.errors and report.refused == []


class _Source:
    def __init__(self, name, refused=(), errors=()):
        self.name, self._refused, self._errors = name, list(refused), list(errors)

    async def fetch(self, start, end):
        report = svc.SourceReport(name=self.name, status="failed" if (self._refused or self._errors) else "ok")
        for r in self._refused:
            report.refuse(r)
        report.errors.extend(self._errors)
        return [], report


class _NoQueryDb:
    def query(self, *a, **k):
        raise AssertionError("nothing was fetched, so nothing may be looked up")

    def commit(self):
        pass

    def rollback(self):
        pass


def _sync(*sources):
    service = svc.EPRSSyncService.__new__(svc.EPRSSyncService)   # no scraper, no DB
    service._db = _NoQueryDb()
    service._owns_db = False
    service.sources = sources
    return asyncio.run(service.sync_all(days=3))


def test_the_exit_code_is_unreachable_only_when_every_error_is_a_refusal():
    script = _script()
    # one source answered, the other did not
    stats = _sync(_Source("thinktank_portal"), _Source("second_source", refused=["Second feed page 1: WAF signature or HTTP 404 (1290 bytes)"]))
    assert (stats["errors"], stats["refused"]) == (1, 1)
    assert stats["refused_details"] == ["second_source: Second feed page 1: WAF signature or HTTP 404 (1290 bytes)"]
    assert script.exit_code_for(stats) == script.EXIT_UNREACHABLE
    # every source refused: still the sites, not the job
    stats = _sync(_Source("thinktank_portal", refused=["Think Tank RSS page 0: HTTP 503"]), _Source("second_source", refused=["Second feed page 1: HTTP 404"]))
    assert stats["nothing_fetched"] and stats["refused"] == stats["errors"]
    assert script.exit_code_for(stats) == script.EXIT_UNREACHABLE
    # one error of ours among the refusals fails as before
    stats = _sync(_Source("thinktank_portal"), _Source("second_source", refused=["Second feed page 1: HTTP 404"], errors=["Blog feed page 2: unparseable 200"]))
    assert script.exit_code_for(stats) == script.EXIT_ERRORS
    stats = _sync(_Source("thinktank_portal", errors=["Think Tank RSS page 0: unparseable 200"]), _Source("second_source", errors=["Second feed page 1: unparseable 200"]))
    assert script.exit_code_for(stats) == script.EXIT_NOTHING_FETCHED


# ---------------------------------------------------- what ended with the blog, 2 Nov 2026

def test_nothing_scheduled_reads_the_discontinued_blog():
    from api import cron
    assert [type(s).__name__ for s in svc.EPRSSyncService(db=object()).sources] == ["ThinkTankPortalSource"]
    assert not hasattr(svc, "BLOG_FEED_URL")
    assert "eprs_legislation" not in cron._WARM_TIER_RECORDED
    assert "sync_eprs_legislation_in_progress" not in (BACKEND / "api" / "cron.py").read_text().replace(
        "`sync_eprs_legislation_in_progress.py` used to run here", "")


# ---------------------------------------------------- WTO: three tries, then a named refusal

def _tbt(monkeypatch, answers):
    from services.scrapers.dg_grow.tbt_scraper import TBTScraper
    scraper = TBTScraper()
    scraper.RETRY_PAUSE_SECONDS = 0
    calls = []

    async def fetch(url, **kw):
        calls.append(url)
        answer = answers[len(calls) - 1]
        if isinstance(answer, Exception):
            raise answer
        return answer
    monkeypatch.setattr(scraper, "_fetch", fetch)
    return scraper, calls


def test_tbt_tries_three_times_and_names_the_refusal(monkeypatch):
    from services.scrapers.base_scraper import ScraperError
    # a hang, then the page: the page is read and nothing is refused
    scraper, calls = _tbt(monkeypatch, [ScraperError("Request timeout for x"), "<html><body></body></html>"])
    assert asyncio.run(scraper.get_latest_eu_notifications(limit=50)) == []
    assert len(calls) == 2 and scraper.refused is None
    # three hangs: no notifications, and the reason is kept
    scraper, calls = _tbt(monkeypatch, [ScraperError("Request timeout for x")] * 3)
    assert asyncio.run(scraper.get_latest_eu_notifications(limit=50)) == []
    assert len(calls) == 3 and "Request timeout" in scraper.refused


def _record(monkeypatch, stats, last_good):
    spec = importlib.util.spec_from_file_location("sync_dg_grow_refusals", BACKEND / "scripts" / "sync_dg_grow.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rows = []
    monkeypatch.setattr(freshness, "record_run", lambda db, **kw: rows.append(kw))
    monkeypatch.setattr(freshness, "last_success_at", lambda db, key: last_good)

    class Db:
        def rollback(self):
            pass
    mod._record_simple(Db(), "wto_tbt", stats, datetime.now(timezone.utc))
    return rows[0]


def test_wto_row_is_degraded_inside_the_grace_and_a_parsed_nothing_still_fails(monkeypatch):
    now = datetime.now(timezone.utc)
    refused = {"synced": 0, "new": 0, "errors": 0, "refused": "3 tries, last: Request timeout"}
    row = _record(monkeypatch, refused, now - timedelta(hours=20))
    assert row["status"] == "degraded" and row["error"].startswith(freshness.UNREACHABLE)
    assert _record(monkeypatch, refused, now - timedelta(hours=80))["status"] == "failed"
    assert _record(monkeypatch, refused, None)["status"] == "failed"
    # the site answered and the parser found nothing: a broken job, at once
    row = _record(monkeypatch, {"synced": 0, "new": 0, "errors": 0}, now - timedelta(hours=1))
    assert (row["status"], row["error"]) == ("failed", "nothing fetched")


# ---------------------------------------------------- ECHA among the bespoke news sources

def _bespoke(monkeypatch, capsys, outcomes, last_good):
    spec = importlib.util.spec_from_file_location("sync_bespoke_refusals", BACKEND / "scripts" / "sync_bespoke_news.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class Db:
        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    class Fetcher:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def scrape(cfg, fetcher):
        answer = outcomes[cfg["institution"]]
        if isinstance(answer, Exception):
            raise answer
        return answer
    monkeypatch.setattr(mod, "SessionLocal", Db)
    monkeypatch.setattr(mod, "WafBrowserFetcher", Fetcher)
    monkeypatch.setattr(mod, "BESPOKE_SOURCES", [{"institution": k} for k in outcomes])
    monkeypatch.setattr(mod, "scrape_bespoke", scrape)
    monkeypatch.setattr(mod, "scrape_eeas", lambda fetcher: [{"entry_key": "e"}])
    monkeypatch.setattr(mod, "date_new_items", lambda db, items, fetcher=None: (items, []))
    monkeypatch.setattr(mod, "_upsert", lambda db, it: "new")
    monkeypatch.setattr(mod, "stamp_fetched", lambda db, keys: None)
    monkeypatch.setattr(mod, "record_refusals", lambda db, key, refused: None)
    monkeypatch.setattr(mod, "last_success_at", lambda db, key: last_good)
    code = mod.main()
    return code, capsys.readouterr().out


def test_an_institutions_outage_is_degraded_and_our_own_error_still_fails(monkeypatch, capsys):
    from services.scrapers.bespoke_news_scraper import BespokeFetchError
    now = datetime.now(timezone.utc)
    ok = [{"entry_key": "a"}]
    outage = BespokeFetchError("ECHA: HTTP 502 from https://echa.europa.eu/news")
    code, out = _bespoke(monkeypatch, capsys, {"ECHA": outage, "EEA": ok}, now - timedelta(hours=10))
    assert code == 0 and "[SYNC_STATUS] degraded: source unreachable (ECHA: HTTP 502" in out
    code, out = _bespoke(monkeypatch, capsys, {"ECHA": outage, "EEA": ok}, now - timedelta(hours=80))
    assert code == 1 and "[SYNC_STATUS]" not in out
    code, out = _bespoke(monkeypatch, capsys, {"ECHA": outage, "EEA": ValueError("our bug")}, now - timedelta(hours=10))
    assert code == 1 and "[SYNC_STATUS]" not in out


# ---------------------------------------------------- Cellar for the eu_laws jobs

def test_cellar_down_is_degraded_and_a_spent_budget_still_fails(monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("refresh_in_force_refusals", BACKEND / "scripts" / "refresh_eu_laws_in_force.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class Rows:
        def fetchall(self):
            return [(1, "32016R0679", True)]

    class Db:
        def execute(self, *a, **k):
            return Rows()

        def rollback(self):
            pass

        def close(self):
            pass

    def run(down):
        def facts(celexes, groups, budget, log):
            if down:
                budget.failed = mod.Budget.FAILS_IN_A_ROW
                raise mod.CellarDown("4 calls in a row failed the control law")
            raise mod.CellarDown("time budget spent")
        monkeypatch.setattr(mod, "cellar_facts", facts)
        monkeypatch.setattr(mod, "SessionLocal", Db)
        monkeypatch.setattr(mod, "last_success_at", lambda db, key: datetime.now(timezone.utc) - timedelta(hours=24))
        monkeypatch.setattr(mod.sys, "argv", ["refresh_eu_laws_in_force.py", "--apply"])
        code = mod.main()
        return code, capsys.readouterr().out

    code, out = run(True)
    assert code == 0 and "[SYNC_STATUS] degraded: source unreachable (Cellar: 4 calls" in out
    code, out = run(False)
    assert code == 1 and "[SYNC_STATUS]" not in out
