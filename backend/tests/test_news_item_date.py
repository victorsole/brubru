"""The shared item-page date chain (services.news.item_date), 11 September 2026.

One chain for two callers: the backfill that repairs stored rows, and the news
writers that must stop new rows arriving undated. No network: every fetch is
stubbed, and each stub that must NOT be reached raises, so a test that passes
proves which step answered.
"""
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
BACKEND = pathlib.Path(_REPO_ROOT) / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.news import item_date  # noqa: E402
from services.news.item_date import presscorner_reference, resolve_item_date  # noqa: E402


class _Resp:
    def __init__(self, text, status=200, ctype="application/json"):
        self.text = text
        self.status_code = status
        self.headers = {"content-type": ctype}


def _never(*_a, **_k):
    raise AssertionError("this step must not be reached")


@pytest.mark.parametrize("url,ref", [
    ("https://ec.europa.eu/commission/presscorner/detail/en/ip_26_1801", "IP/26/1801"),
    ("https://ec.europa.eu/commission/presscorner/detail/en/statement_26_1090", "STATEMENT/26/1090"),
    ("https://ec.europa.eu/commission/presscorner/detail/en/speech_26_1016", "SPEECH/26/1016"),
    ("https://ec.europa.eu/commission/presscorner/detail/en/qanda_26_1141", "QANDA/26/1141"),
    # A MEX daily-news item carries a fragment; one stored URL is upper-case.
    ("https://ec.europa.eu/commission/presscorner/detail/en/mex_24_1307#11", "MEX/24/1307"),
    ("https://ec.europa.eu/commission/presscorner/detail/en/IP_26_1637", "IP/26/1637"),
    ("https://ec.europa.eu/commission/presscorner/home/en", None),
    ("https://digital-strategy.ec.europa.eu/en/news/some-article", None),
])
def test_presscorner_reference(url, ref):
    assert presscorner_reference(url) == ref


def test_presscorner_items_are_dated_from_the_api(monkeypatch):
    monkeypatch.setattr(item_date, "http_get", lambda u: _Resp('{"eventDate": "2026-09-07"}'))
    monkeypatch.setattr(item_date, "escalating_get", _never)
    dt, prov = resolve_item_date("https://ec.europa.eu/commission/presscorner/detail/en/ip_26_1801")
    assert (dt.date().isoformat(), prov) == ("2026-09-07", "presscorner_api")


def test_a_presscorner_api_miss_falls_through_to_the_page(monkeypatch):
    monkeypatch.setattr(item_date, "http_get", lambda u: _Resp("{}"))
    monkeypatch.setattr(item_date, "escalating_get", lambda u, fetcher=None, **kw:
                        '<script type="application/ld+json">{"datePublished": "2026-08-31T10:00:00Z"}</script>')
    monkeypatch.setattr(item_date, "browser_get", _never)
    dt, prov = resolve_item_date("https://ec.europa.eu/commission/presscorner/detail/en/ip_26_1771")
    assert (dt.date().isoformat(), prov) == ("2026-08-31", "jsonld_datePublished")


def test_a_future_event_date_is_not_a_publication_date(monkeypatch):
    future = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
    monkeypatch.setattr(item_date, "http_get", lambda u: _Resp(f'{{"eventDate": "{future}"}}'))
    monkeypatch.setattr(item_date, "escalating_get", lambda u, fetcher=None, **kw: None)
    assert resolve_item_date("https://ec.europa.eu/commission/presscorner/detail/en/ip_26_9999") == (None, "fetch_failed")


def test_a_dated_static_page_is_not_rendered(monkeypatch):
    monkeypatch.setattr(item_date, "escalating_get", lambda u, fetcher=None, **kw:
                        '<p><time datetime="2026-09-11T00:05:00Z" class="datetime">11/09/2026</time></p>')
    monkeypatch.setattr(item_date, "browser_get", _never)
    dt, prov = resolve_item_date("https://osha.europa.eu/en/oshnews/back-school-oira-healthier-workplaces-education")
    assert (dt.date().isoformat(), prov) == ("2026-09-11", "time_datetime")


def test_an_undated_static_page_is_rendered_before_giving_up(monkeypatch):
    monkeypatch.setattr(item_date, "escalating_get", lambda u, fetcher=None, **kw: "<html><body>no date here</body></html>")
    monkeypatch.setattr(item_date, "browser_get", lambda u, fetcher=None, **kw:
                        '<time class="date" datetime="09/09/2026">9 September</time>')
    dt, prov = resolve_item_date("https://www.eca.europa.eu/en/news/NEWS-SR-2026-21")
    assert (dt.date().isoformat(), prov) == ("2026-09-09", "time_datetime_rendered")


def test_a_page_with_no_carrier_anywhere_says_so(monkeypatch):
    # INTPA stories, 11 Sep 2026: no date static or rendered.
    monkeypatch.setattr(item_date, "escalating_get", lambda u, fetcher=None, **kw: "<html>story</html>")
    monkeypatch.setattr(item_date, "browser_get", lambda u, fetcher=None, **kw: "<html>story, rendered</html>")
    url = "https://international-partnerships.ec.europa.eu/news-and-events/stories/brazilian-public-defenders-give-migrants-new-hope_en"
    assert resolve_item_date(url) == (None, "no_carrier")


def test_render_false_never_opens_a_browser(monkeypatch):
    # A page with no date: with render=False the resolver must stop, not render.
    monkeypatch.setattr(item_date, "http_get", lambda u: _Resp("<html>" + "x" * 3000 + "</html>", ctype="text/html"))
    monkeypatch.setattr(item_date, "browser_get", _never)
    assert resolve_item_date("https://www.eeas.europa.eu/x_en", render=False) == (None, "no_carrier")


def test_a_wall_without_rendering_is_a_fetch_failure_not_a_browser_launch(monkeypatch):
    monkeypatch.setattr(item_date, "http_get", lambda u: _Resp("", status=429, ctype="text/html"))
    monkeypatch.setattr(item_date, "cffi_get", lambda u: None)
    monkeypatch.setattr(item_date, "browser_get", _never)
    assert resolve_item_date("https://www.eeas.europa.eu/x_en", render=False) == (None, "fetch_failed")


def test_a_fetch_failure_is_named_not_guessed(monkeypatch):
    monkeypatch.setattr(item_date, "escalating_get", lambda u, fetcher=None, **kw: None)
    monkeypatch.setattr(item_date, "browser_get", _never)
    assert resolve_item_date("https://www.cor.europa.eu/en/news/gone") == (None, "fetch_failed")


def test_a_pdf_is_not_parsed_as_html(monkeypatch):
    monkeypatch.setattr(item_date, "escalating_get", _never)
    url = "https://curia.europa.eu/site/upload/docs/application/pdf/2026-09/cp260123en.pdf"
    assert resolve_item_date(url) == (None, "pdf_not_read")


def test_no_url_is_an_answer_not_a_crash():
    assert resolve_item_date("") == (None, "no_url")


def test_an_open_browser_is_reused_with_full_html(monkeypatch):
    calls = []

    class _Fetcher:
        def fetch(self, url, **kw):
            calls.append(kw)
            return type("R", (), {"html": "<html>rendered</html>"})()

    monkeypatch.setattr(item_date, "_waf_module", _never)   # no second Chromium
    assert item_date.browser_get("https://example.europa.eu/x", fetcher=_Fetcher()) == "<html>rendered</html>"
    assert calls == [{"expand_accordions": False, "strip_chrome": False}]


class _FakeWaf:
    """Stands in for waf_browser_fetcher: counts launches, pages and closes."""
    def __init__(self):
        self.entered = 0
        self.exited = 0
        self.pages = []
        outer = self

        class WafBrowserFetcher:
            def __init__(self, **kw):
                self.kw = kw

            def __enter__(self):
                outer.entered += 1
                return self

            def __exit__(self, *a):
                outer.exited += 1

            def fetch(self, url, **kw):
                outer.pages.append(url)
                return type("R", (), {"html": f"<html>{url}</html>"})()

        self.WafBrowserFetcher = WafBrowserFetcher


def test_lazy_browser_launches_nothing_until_a_page_needs_rendering(monkeypatch):
    fake = _FakeWaf()
    monkeypatch.setattr(item_date, "_waf_module", lambda: fake)
    b = item_date.LazyBrowser()
    b.close()
    assert (fake.entered, b.launches) == (0, 0)


def test_lazy_browser_reuses_one_browser_and_restarts_on_schedule(monkeypatch):
    fake = _FakeWaf()
    monkeypatch.setattr(item_date, "_waf_module", lambda: fake)
    b = item_date.LazyBrowser(restart_every=3, settle_ms=10)
    for n in range(7):
        assert item_date.browser_get(f"https://x.europa.eu/{n}", fetcher=b) == f"<html>https://x.europa.eu/{n}</html>"
    # 7 pages at 3 per browser: launched for pages 1, 4 and 7; two closed on restart.
    assert (b.launches, fake.entered, fake.exited) == (3, 3, 2)
    b.close()
    assert fake.exited == 3
    b.close()                      # closing twice is harmless
    assert fake.exited == 3


def test_the_backfill_holds_one_lazy_browser():
    import inspect
    from scripts import backfill_news_document_dates as bf
    src = inspect.getsource(bf.main)
    assert "LazyBrowser(" in src and "fetcher=browser" in src and "browser.close()" in src


def test_the_backfill_runs_the_same_chain():
    from scripts import backfill_news_document_dates as bf
    assert bf.resolve_item_date is item_date.resolve_item_date
    assert bf._escalating_get is item_date.escalating_get
    assert bf._browser_get is item_date.browser_get
    assert bf._cffi_get is item_date.cffi_get
