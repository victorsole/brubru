"""The write guard: a NEW news row is dated or not written (11 September 2026).

No network and no database: the resolver and the ledger are stubbed, and a stub
that must not be reached raises, so a passing test proves which path ran.
"""
import pathlib
import sys
from datetime import date, datetime, timezone
from types import SimpleNamespace

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
BACKEND = pathlib.Path(_REPO_ROOT) / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.news import write_guard  # noqa: E402
from services.news.write_guard import REFUSAL_SOURCE_SUFFIX, date_new_items, record_refusals  # noqa: E402


class _Db:
    """Answers the one existence query with the keys it was built with."""
    def __init__(self, existing=()):
        self.existing = set(existing)
        self.queries = 0

    def execute(self, _stmt, params):
        self.queries += 1
        return [(k,) for k in params["k"] if k in self.existing]


class _NoDb:
    def execute(self, *_a, **_k):
        raise AssertionError("no query expected")


def _never(*_a, **_k):
    raise AssertionError("the resolver must not be called")


def _item(key, nd=None, url=None, sk="ACER"):
    return {"entry_key": key, "news_date": nd, "source_url": url or f"https://x.europa.eu/{key}",
            "source_key": sk, "title": key}


def test_dated_items_pass_without_a_query(monkeypatch):
    monkeypatch.setattr(write_guard, "resolve_item_date", _never)
    items = [_item("a", date(2026, 9, 10)), _item("b", date(2026, 9, 9))]
    keep, refused = date_new_items(_NoDb(), items)
    assert (keep, refused) == (items, [])


def test_an_existing_undated_row_is_left_alone(monkeypatch):
    # Stock rows are the backfill's job; refusing here would only block a title fix.
    monkeypatch.setattr(write_guard, "resolve_item_date", _never)
    keep, refused = date_new_items(_Db(existing={"old"}), [_item("old")])
    assert [i["entry_key"] for i in keep] == ["old"] and refused == []
    assert keep[0]["news_date"] is None


def test_a_new_undated_item_is_dated_from_its_own_page(monkeypatch):
    seen = {}

    def _resolve(url, fetcher=None):
        seen["url"], seen["fetcher"] = url, fetcher
        return datetime(2026, 9, 10, 8, 30, tzinfo=timezone.utc), "jsonld_datePublished"

    monkeypatch.setattr(write_guard, "resolve_item_date", _resolve)
    browser = object()
    keep, refused = date_new_items(_Db(), [_item("new", url="https://www.europol.europa.eu/n")], fetcher=browser)
    assert refused == [] and keep[0]["news_date"] == date(2026, 9, 10)
    assert seen == {"url": "https://www.europol.europa.eu/n", "fetcher": browser}


def test_a_new_item_nobody_can_date_is_refused_with_the_reason(monkeypatch):
    monkeypatch.setattr(write_guard, "resolve_item_date", lambda u, fetcher=None: (None, "no_carrier"))
    items = [_item("dated", date(2026, 9, 1)), _item("story", sk="COR")]
    keep, refused = date_new_items(_Db(), items)
    assert [i["entry_key"] for i in keep] == ["dated"]
    assert [(i["entry_key"], i["undated_reason"]) for i in refused] == [("story", "no_carrier")]


def test_the_existence_check_is_one_query_for_the_whole_batch(monkeypatch):
    monkeypatch.setattr(write_guard, "resolve_item_date", lambda u, fetcher=None: (None, "no_carrier"))
    db = _Db(existing={"k1"})
    date_new_items(db, [_item("k1"), _item("k2"), _item("k3")])
    assert db.queries == 1


def test_no_refusals_writes_no_ledger_row(monkeypatch):
    monkeypatch.setattr(write_guard, "record_run", _never)
    record_refusals(object(), "news_bespoke", [])


def test_refusals_are_recorded_as_a_failure_outside_every_feed(monkeypatch):
    from services.sync.source_registry import MEUB_SOURCES
    calls = []
    monkeypatch.setattr(write_guard, "record_run", lambda db, **kw: calls.append(kw))
    refused = [dict(_item(f"s{n}", sk="COR"), undated_reason="no_carrier") for n in range(45)]
    record_refusals(object(), "news_bespoke", refused)
    assert len(calls) == 1
    row = calls[0]
    assert row["status"] == "failed" and row["tier"] is None and row["items_added"] == 0
    assert row["source_key"] == "news_bespoke" + REFUSAL_SOURCE_SUFFIX
    # Not a registered feed, so no freshness chip turns stale over one undatable story.
    assert row["source_key"] not in {s.key for s in MEUB_SOURCES}
    assert "45 new news item(s) NOT written" in row["error"]
    assert "COR  no_carrier  https://x.europa.eu/s0" in row["error"]
    assert row["error"].endswith("...and 5 more")


class _Ledger:
    """Answers the one 'last refusal row' query with the text it was built with."""
    def __init__(self, last_error):
        self.last_error = last_error

    def execute(self, _stmt, _params):
        return SimpleNamespace(scalar=lambda: self.last_error)


def _recorded_status(monkeypatch, db, refused):
    calls = []
    monkeypatch.setattr(write_guard, "record_run", lambda db, **kw: calls.append(kw))
    record_refusals(db, "economy_satcen", refused)
    assert len(calls) == 1
    return calls[0]["status"], calls[0]["error"]


def test_the_same_items_refused_again_are_a_standing_gap_not_a_new_failure(monkeypatch):
    # 13 Oct 2026: the same 8 undatable items turned the hourly cron red every day
    # for three weeks. Said once as a failure; after that, degraded.
    refused = [dict(_item(f"s{n}", sk="satcen/news"), undated_reason="no_carrier") for n in range(4)]
    first, text_ = _recorded_status(monkeypatch, _Ledger(None), refused)
    assert first == "failed"
    again, _ = _recorded_status(monkeypatch, _Ledger(text_), refused)
    assert again == "degraded"
    # One of them got a date and is no longer refused: the rest are still known.
    fewer, _ = _recorded_status(monkeypatch, _Ledger(text_), refused[:3])
    assert fewer == "degraded"


def test_a_newly_refused_item_is_a_failure_again(monkeypatch):
    refused = [dict(_item(f"s{n}", sk="satcen/news"), undated_reason="no_carrier") for n in range(4)]
    _, text_ = _recorded_status(monkeypatch, _Ledger(None), refused)
    one_more = refused + [dict(_item("new", sk="satcen/news"), undated_reason="no_carrier")]
    status, _ = _recorded_status(monkeypatch, _Ledger(text_), one_more)
    assert status == "failed"


def test_a_list_too_long_to_name_or_an_unreadable_ledger_stays_a_failure(monkeypatch):
    many = [dict(_item(f"s{n}", sk="COR"), undated_reason="no_carrier") for n in range(45)]
    _, text_ = _recorded_status(monkeypatch, _Ledger(None), many)
    # 45 refused, 40 named: nothing proves the other 5 were reported before.
    assert _recorded_status(monkeypatch, _Ledger(text_), many)[0] == "failed"

    class _Broken:
        def execute(self, *_a, **_k):
            raise RuntimeError("ledger unreachable")
    few = many[:2]
    assert _recorded_status(monkeypatch, _Broken(), few)[0] == "failed"
    # A URL that only shares a prefix with a reported one is not that item.
    _, reported = _recorded_status(monkeypatch, _Ledger(None), few)
    lookalike = [dict(few[0], source_url=few[0]["source_url"] + "-part-2")]
    assert _recorded_status(monkeypatch, _Ledger(reported), lookalike)[0] == "failed"


# --- economy_items: the same rule in sync_economy ----------------------------

def test_economy_new_undated_news_is_dated_or_refused(monkeypatch):
    import scripts.sync_economy as se
    monkeypatch.setattr(se, "_UNDATED_REFUSED", [])
    when = datetime(2026, 9, 10, tzinfo=timezone.utc)

    def it(nd=None):
        return SimpleNamespace(document_date=nd)

    by_url = {
        ("europol", "news", "https://e/new-datable"): it(),
        ("europol", "news", "https://e/new-undatable"): it(),
        ("europol", "news", "https://e/stock-undated"): it(),
        ("europol", "press_release", "https://e/already-dated"): it(when),
        ("europol", "event", "https://e/event-undated"): it(),
    }
    resolved = []

    def _resolve(url):
        resolved.append(url)
        return (when, "jsonld_datePublished") if url.endswith("new-datable") else (None, "no_carrier")

    refused = se._refuse_undated_new_news(
        by_url, existing_fn=lambda keys: {("europol", "news", "https://e/stock-undated")},
        resolve=_resolve)

    assert by_url[("europol", "news", "https://e/new-datable")].document_date == when
    assert ("europol", "news", "https://e/new-undatable") not in by_url
    assert by_url[("europol", "news", "https://e/stock-undated")].document_date is None
    assert by_url[("europol", "event", "https://e/event-undated")].document_date is None
    # Only NEW undated NEWS rows cost a fetch: not stock, not dated rows, not events.
    assert sorted(resolved) == ["https://e/new-datable", "https://e/new-undatable"]
    assert refused == [{"source_key": "europol/news", "undated_reason": "no_carrier",
                        "source_url": "https://e/new-undatable"}]
    assert se._UNDATED_REFUSED == refused


def test_economy_guard_makes_no_query_when_nothing_is_undated(monkeypatch):
    import scripts.sync_economy as se
    monkeypatch.setattr(se, "_UNDATED_REFUSED", [])
    by_url = {("ecb", "news", "https://e/a"): SimpleNamespace(document_date=datetime(2026, 9, 1, tzinfo=timezone.utc))}
    assert se._refuse_undated_new_news(by_url, existing_fn=_never, resolve=_never) == []


# --- another website's page is a warning (20 Oct 2026) ------------------------

EDPS_EVENT = "https://www.maastrichtuniversity.nl/events/ecpc-10th-anniversary-conference"


def test_a_refused_page_on_another_website_is_a_warning_not_a_failure(monkeypatch):
    # 19 Oct 2026: EDPS's news listing linked a Maastricht University event page with no
    # date. Refusing it was right; recording it `failed` turned the cron red.
    import scripts.sync_economy as se
    monkeypatch.setattr(se, "_UNDATED_REFUSED", [])
    when = datetime(2026, 10, 15, tzinfo=timezone.utc)
    by_url = {("edps", "news", f"https://www.edps.europa.eu/press-publications/press-news/news/2026/n{n}_en"):
              SimpleNamespace(document_date=when) for n in range(9)}
    by_url[("edps", "news", EDPS_EVENT)] = SimpleNamespace(document_date=None)
    refused = se._refuse_undated_new_news(by_url, existing_fn=lambda keys: set(),
                                          resolve=lambda url: (None, "no_carrier"))
    assert refused == [{"source_key": "edps/news", "undated_reason": "no_carrier",
                        "source_url": EDPS_EVENT, "off_site": True}]
    status, text_ = _recorded_status(monkeypatch, _Ledger(None), refused)
    assert status == "degraded"
    assert EDPS_EVENT in text_ and "(another website)" in text_


def test_a_refused_page_on_the_sources_own_site_is_still_a_failure(monkeypatch):
    import scripts.sync_economy as se
    monkeypatch.setattr(se, "_UNDATED_REFUSED", [])
    own = "https://www.clean-aviation.eu/discover-our-highlights-2025-2026-0"
    by_url = {("aviation", "news", f"https://www.clean-aviation.eu/news-{n}"):
              SimpleNamespace(document_date=datetime(2026, 10, 1, tzinfo=timezone.utc)) for n in range(5)}
    by_url[("aviation", "news", own)] = SimpleNamespace(document_date=None)
    refused = se._refuse_undated_new_news(by_url, existing_fn=lambda keys: set(),
                                          resolve=lambda url: (None, "no_carrier"))
    assert "off_site" not in refused[0]
    assert _recorded_status(monkeypatch, _Ledger(None), refused)[0] == "failed"


def test_an_own_site_item_among_off_site_ones_keeps_the_run_a_failure(monkeypatch):
    refused = [dict(_item("a", url=EDPS_EVENT), undated_reason="no_carrier", off_site=True),
               dict(_item("b", url="https://www.edps.europa.eu/news/b"), undated_reason="no_carrier")]
    assert _recorded_status(monkeypatch, _Ledger(None), refused)[0] == "failed"
    # Once the own-site item was named, the same pair is a standing gap.
    _, text_ = _recorded_status(monkeypatch, _Ledger(None), refused)
    assert _recorded_status(monkeypatch, _Ledger(text_), refused)[0] == "degraded"


def test_nothing_is_marked_off_site_without_a_listing_to_compare():
    lone = [{"source_url": EDPS_EVENT}]
    write_guard.mark_off_site(lone, [EDPS_EVENT])
    assert "off_site" not in lone[0]
    two_hosts = [{"source_url": EDPS_EVENT}]
    write_guard.mark_off_site(two_hosts, [EDPS_EVENT, "https://www.edps.europa.eu/news/x"])
    assert "off_site" not in two_hosts[0]   # one item each: no host is the listing's own


def test_the_news_writers_mark_off_site_pages_too(monkeypatch):
    items = [_item(f"k{n}", url=f"https://commission.europa.eu/news/{n}") for n in range(4)]
    items.append(_item("ext", url=EDPS_EVENT))
    monkeypatch.setattr(write_guard, "resolve_item_date", lambda url, fetcher=None: (None, "no_carrier"))
    _, refused = date_new_items(_Db(set()), items)
    by_url = {i["source_url"]: i for i in refused}
    assert by_url[EDPS_EVENT].get("off_site") is True
    assert "off_site" not in by_url["https://commission.europa.eu/news/0"]


def test_another_europa_eu_site_is_not_off_site():
    # An EDPS story on transparency-register.europa.eu is still an EU page we should date.
    item = [{"source_url": "https://transparency-register.europa.eu/news/x_en"}]
    listed = [f"https://www.edps.europa.eu/news/{n}" for n in range(5)] + [item[0]["source_url"]]
    write_guard.mark_off_site(item, listed)
    assert "off_site" not in item[0]
