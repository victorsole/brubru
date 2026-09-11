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
