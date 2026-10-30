"""A site that will not serve us is degraded for 72 hours after the job's last good run, then fails.

30 Oct 2026 (Victor's decision): epthinktank.eu, the EPRS blog and its "EU legislation in
progress" page, stopped answering on 29 Oct (a timeout from one machine, a refused connection
from another, a 1,290-byte refusal on Railway). The two EPRS jobs failed at every warm run and,
failing twice in a row, made the cron red twice a day. A refusal (a timeout, a refused
connection, a WAF page, an HTTP error status) is now recorded `degraded` with its reason while
the job's last success is under 72 hours old, and fails after. A page that answers but does not
parse is never a refusal: it fails at once, as before."""
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


def test_a_blog_feed_refusal_is_marked_and_an_unparseable_page_is_not():
    async def not_found(url, params=None):
        return 404, "x" * 1290

    async def refused(url, params=None):
        raise ConnectionRefusedError("connect ECONNREFUSED")

    async def garbage(url, params=None):
        return 200, "<html>not a feed</html>"

    for http_get in (not_found, refused):
        _, report = asyncio.run(svc.EPRSBlogFeedSource(http_get=http_get).fetch(START, END))
        assert report.status == "failed" and report.refused == report.errors and report.errors
    _, report = asyncio.run(svc.EPRSBlogFeedSource(http_get=garbage).fetch(START, END))
    assert report.errors and report.refused == []


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


def _sync(portal, blog):
    service = svc.EPRSSyncService.__new__(svc.EPRSSyncService)   # no scraper, no DB
    service._db = _NoQueryDb()
    service._owns_db = False
    service.portal_source, service.blog_source = portal, blog
    return asyncio.run(service.sync_all(days=3))


def test_the_exit_code_is_unreachable_only_when_every_error_is_a_refusal():
    script = _script()
    # 30 Oct 2026: the portal answered, the blog feed did not
    stats = _sync(_Source("thinktank_portal"), _Source("epthinktank_blog", refused=["Blog feed page 1: WAF signature or HTTP 404 (1290 bytes)"]))
    assert (stats["errors"], stats["refused"]) == (1, 1)
    assert stats["refused_details"] == ["epthinktank_blog: Blog feed page 1: WAF signature or HTTP 404 (1290 bytes)"]
    assert script.exit_code_for(stats) == script.EXIT_UNREACHABLE
    # every source refused: still the sites, not the job
    stats = _sync(_Source("thinktank_portal", refused=["Think Tank RSS page 0: HTTP 503"]), _Source("epthinktank_blog", refused=["Blog feed page 1: HTTP 404"]))
    assert stats["nothing_fetched"] and stats["refused"] == stats["errors"]
    assert script.exit_code_for(stats) == script.EXIT_UNREACHABLE
    # one error of ours among the refusals fails as before
    stats = _sync(_Source("thinktank_portal"), _Source("epthinktank_blog", refused=["Blog feed page 1: HTTP 404"], errors=["Blog feed page 2: unparseable 200"]))
    assert script.exit_code_for(stats) == script.EXIT_ERRORS
    stats = _sync(_Source("thinktank_portal", errors=["Think Tank RSS page 0: unparseable 200"]), _Source("epthinktank_blog", errors=["Blog feed page 1: unparseable 200"]))
    assert script.exit_code_for(stats) == script.EXIT_NOTHING_FETCHED
