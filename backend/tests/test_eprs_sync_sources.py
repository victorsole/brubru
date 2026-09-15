"""EPRS publications sync: sources must never report a WAF wall as an empty feed.

Incident (15 Sep 2026): the EP Think Tank RSS answered HTTP 202 with an empty
body from ~23 July; the sync printed "Added 0, Updated 0, Skipped 34, Errors 0"
for eight weeks while eprs_publications froze at 21 July.

Fixtures are real pages captured on 15 Sep 2026 (window 21/07/2026-15/09/2026,
the four publication types).
"""

import asyncio
import importlib.util
import pathlib
import sys
from datetime import datetime

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.scrapers import eprs_sync_service as svc  # noqa: E402
from models.eprs_publication import EPRSPublicationTypeEnum  # noqa: E402

FIXTURES = BACKEND / "tests" / "fixtures" / "eprs"
LISTING_HTML = (FIXTURES / "thinktank_listing_2026_09_15.html").read_text(encoding="utf-8")
RSS_XML = (FIXTURES / "thinktank_rss_2026_09_15.xml").read_text(encoding="utf-8")

START = datetime(2026, 7, 21)
END = datetime(2026, 9, 16)


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- parsers

def test_listing_parser_on_saved_fixture():
    items, total = svc.parse_thinktank_listing(LISTING_HTML)
    assert total == 66
    assert len(items) == 10
    first = items[0]
    assert first["reference"] == "EPRS_BRI(2026)791484"
    assert first["title"] == "Is Nepal's young leader meeting expectations of change?"
    assert first["publication_type"] is EPRSPublicationTypeEnum.BRIEFING
    assert first["publication_date"] == datetime(2026, 9, 14)
    assert first["link"] == "https://www.europarl.europa.eu/thinktank/en/document/EPRS_BRI(2026)791484"
    assert first["summary"].startswith("Nepal's leader is the world's youngest")
    refs = [i["reference"] for i in items]
    assert "EPRS_ATA(2026)791482" in refs            # European Heritage Days
    assert "EPRS_BRI(2026)791485" in refs            # Article 2 TEU
    assert "EPRS_BRI(2026)788156" in refs            # ETS 2026 revision IA
    heritage = next(i for i in items if i["reference"] == "EPRS_ATA(2026)791482")
    assert heritage["publication_type"] is EPRSPublicationTypeEnum.AT_A_GLANCE
    assert all(i["publication_date"] is not None for i in items)


def test_rss_parser_strips_type_prefix_date_suffix_and_source_trailer():
    items = svc.parse_thinktank_rss(RSS_XML)
    assert len(items) == 25
    first = items[0]
    assert first["reference"] == "EPRS_BRI(2026)791484"
    assert first["title"] == "Is Nepal's young leader meeting expectations of change?"
    assert first["publication_date"] == datetime(2026, 9, 14)   # not 13 Sep 22:00 GMT
    assert "Source" not in first["summary"] and "<br" not in first["summary"]
    assert {i["publication_type"] for i in items} <= set(EPRSPublicationTypeEnum)
    assert all(i["publication_type"] is not EPRSPublicationTypeEnum.OTHER for i in items)


@pytest.mark.parametrize("body", ["", "   ", "<html><body>Just a moment</body></html>", "not xml <"])
def test_rss_parser_refuses_non_rss_bodies(body):
    with pytest.raises(svc.UnparseableSourceError):
        svc.parse_thinktank_rss(body)


def test_rss_parser_accepts_a_genuinely_empty_channel():
    empty = '<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>'
    assert svc.parse_thinktank_rss(empty) == []


@pytest.mark.parametrize("body", ["", "<html><body><div>challenge</div></body></html>"])
def test_listing_parser_refuses_walled_pages(body):
    with pytest.raises(svc.UnparseableSourceError):
        svc.parse_thinktank_listing(body)


@pytest.mark.parametrize("status,body,expected", [
    (202, "", True), (403, "blocked", True), (429, "", True), (503, "", True),
    (200, "", True), (200, "  \n", True), (200, "<rss/>", False), (404, "", False),
])
def test_is_waf_response(status, body, expected):
    assert svc.is_waf_response(status, body) is expected


# ---------------------------------------------------------------- routing

class _FakeResult:
    def __init__(self, html, error=None):
        self.html, self.error, self.nav_status = html, error, 200


class _FakeWafModule:
    def __init__(self, html_by_page=None, fail=False):
        self.urls = []
        self.html_by_page = html_by_page or {}
        self.fail = fail
        outer = self

        class WafBrowserFetcher:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def fetch(self, url, **kwargs):
                outer.urls.append(url)
                if outer.fail:
                    return _FakeResult("", error="TimeoutError: challenge never cleared")
                page = int(url.split("page=")[1]) if "page=" in url else 0
                return _FakeResult(outer.html_by_page.get(page, outer.html_by_page.get("default", "")))

        self.WafBrowserFetcher = WafBrowserFetcher


def _single_page_listing():
    # The fixture says "of 66"; make it a one-page window so the fake does not
    # have to serve seven pages.
    return LISTING_HTML.replace("Showing 10 of 66 results", "Showing 10 of 10 results")


def test_waf_202_rss_triggers_playwright_fallback_and_counts_an_error():
    calls = []

    async def http_get(url, params=None):
        calls.append(url)
        return 202, ""                      # the WAF signature on every plain route

    waf = _FakeWafModule(html_by_page={0: _single_page_listing()})
    source = svc.ThinkTankPortalSource(http_get=http_get, waf_module_loader=lambda: waf)
    items, report = _run(source.fetch(START, END))

    assert calls[0] == svc.THINKTANK_RSS_URL and svc.THINKTANK_LISTING_URL in calls
    assert waf.urls, "Playwright fallback was never invoked"
    assert report.status == "ok" and report.via == "playwright"
    assert len(items) == 10 and report.fetched == 10
    assert any("WAF signature (HTTP 202, 0 bytes)" in e for e in report.errors)


def test_unparseable_200_rss_falls_back_to_plain_listing():
    async def http_get(url, params=None):
        if url == svc.THINKTANK_RSS_URL:
            return 200, "<html>JS challenge</html>"
        return 200, _single_page_listing()

    source = svc.ThinkTankPortalSource(http_get=http_get,
                                       waf_module_loader=lambda: pytest.fail("no browser needed"))
    items, report = _run(source.fetch(START, END))
    assert report.status == "ok" and report.via == "listing" and len(items) == 10
    assert any("unparseable 200" in e for e in report.errors)


def test_healthy_rss_is_used_without_errors_and_paginates():
    pages = []

    async def http_get(url, params=None):
        assert url == svc.THINKTANK_RSS_URL
        page = int(dict(params).get("page", 0))
        pages.append(page)
        if page == 0:
            return 200, RSS_XML          # 25 items: a full page, so page 1 is requested
        return 200, '<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'

    source = svc.ThinkTankPortalSource(http_get=http_get,
                                       waf_module_loader=lambda: pytest.fail("no browser needed"))
    items, report = _run(source.fetch(START, END))
    assert pages == [0, 1]
    assert report.status == "ok" and report.via == "rss" and report.errors == []
    assert len(items) == 25


def test_every_route_walled_fails_the_source():
    async def http_get(url, params=None):
        return 202, ""

    source = svc.ThinkTankPortalSource(http_get=http_get,
                                       waf_module_loader=lambda: _FakeWafModule(fail=True))
    items, report = _run(source.fetch(START, END))
    assert items == [] and report.status == "failed"
    assert len(report.errors) == 3          # RSS, plain listing, Playwright


def test_blog_feed_202_is_a_failed_source_not_an_empty_one():
    async def http_get(url, params=None):
        return 202, ""

    items, report = _run(svc.EPRSBlogFeedSource(http_get=http_get).fetch(START, END))
    assert items == [] and report.status == "failed" and report.errors


# ---------------------------------------------------------------- sync + exit code

class _FailingSource:
    def __init__(self, name):
        self.name = name

    async def fetch(self, start, end):
        return [], svc.SourceReport(name=self.name, status="failed",
                                    errors=["WAF signature (HTTP 202, 0 bytes)"])


class _NoQueryDb:
    def query(self, *a, **k):
        raise AssertionError("nothing was fetched, so nothing may be looked up")

    def commit(self):
        pass

    def rollback(self):
        pass


def _load_script():
    path = BACKEND / "scripts" / "sync_eprs_publications.py"
    spec = importlib.util.spec_from_file_location("sync_eprs_publications_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_sync_all_with_every_source_walled_reports_errors_and_exits_non_zero():
    service = svc.EPRSSyncService.__new__(svc.EPRSSyncService)   # no scraper, no DB
    service._db = _NoQueryDb()
    service._owns_db = False
    service.portal_source = _FailingSource("thinktank_portal")
    service.blog_source = _FailingSource("epthinktank_blog")

    stats = _run(service.sync_all(days=7))
    assert stats["nothing_fetched"] is True
    assert stats["skipped"] == 0 and stats["fetched"] == 0
    assert stats["errors"] >= 2

    script = _load_script()
    assert script.exit_code_for(stats) == script.EXIT_NOTHING_FETCHED != 0
    assert script.exit_code_for({"errors": 1, "nothing_fetched": False}) == 1
    assert script.exit_code_for({"errors": 0, "nothing_fetched": False, "skipped": 34}) == 0
