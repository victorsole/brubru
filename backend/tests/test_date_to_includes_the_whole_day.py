"""An upper date bound ("to", "until", "published_to", "deadline_to", ...) includes its whole day.

The defect (found 15 Sep 2026): these filters are documented as "on/before this DATE",
but the columns behind them are timestamps. `col <= '2026-07-24'` compares against
midnight at the START of the day, so every item with a time on that day was dropped:
the ECB's 8 news items of 24 Jul 2026 came back as 0 for from=to=2026-07-24. The same
`<=` shape sat on 21 filters across v1 and v2 (209,190 timed economy_items rows, every
comitology meeting, most tender and call deadlines).

The test goes through each ROUTE, never a copy of its SQL. It takes a witness item
from the route's own pages, one whose date has a time of day, and checks the
boundary through the route:

  * a range route: count(d..d) + count(d+1..d+1) == count(d..d+1). With the bug the
    left side loses day d's timed items, so the sides differ.
  * a before-only route: count(<= d) > count(<= d-1), because the witness is on d.
"""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from api.v1._deps import api_user_with_rate_limit
from main import app
from models.user import User

# (path, lower param, upper param, date field, extra params)
RANGE_CASES = [
    # euipo: one of the bodies whose news carries a time of day (569 rows on 15 Sep).
    ("/api/v2/euipo/news", "since", "until", "document_date", {}),
    ("/api/v2/interoperable/news", "since", "until", "document_date", {}),
    ("/api/v2/consultations/all", "from", "to", "document_date", {}),
    ("/api/v2/events/all", "from", "to", "document_date", {}),
    ("/api/v2/funding/all", "since", "until", "document_date", {}),
    ("/api/v1/specialised/comitology/documents", "meeting_from", "meeting_to", "meeting_start_date", {}),
    ("/api/commission-documents/items", "date_from", "date_to", "publication_date", {}),
    ("/api/texts-adopted/items", "date_from", "date_to", "adoption_date", {}),
    ("/api/v1/eprs", "published_from", "published_to", "publication_date", {}),
    ("/api/v1/research-publications", "published_from", "published_to", "publication_date", {}),
    ("/api/v1/ft-calls-for-proposals", "deadline_from", "deadline_to", "deadline", {}),
    ("/api/v1/ft-calls-for-tenders", "deadline_from", "deadline_to", "deadline", {}),
    ("/api/v1/funding-opportunities", "deadline_from", "deadline_to", "deadline", {}),
    ("/api/v2/funding/startups", "deadline_from", "deadline_to", "deadline", {}),
    ("/api/v1/tenders", "deadline_from", "deadline_to", "submission_deadline", {}),
    ("/api/v1/tenders", "published_from", "published_to", "publication_date", {}),
    ("/api/v1/amendments", "published_from", "published_to", "document_date", {}),
    ("/api/v1/ep-documents", "published_from", "published_to", "document_date", {}),
    ("/api/v1/reports", "published_from", "published_to", "document_date", {}),
    ("/api/v1/opinions", "published_from", "published_to", "document_date", {}),
]


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(
        email="test@example.com", role="admin"
    )
    yield TestClient(app)
    app.dependency_overrides.pop(api_user_with_rate_limit, None)


def _items(body: dict) -> list:
    return body.get("data") or body.get("items") or []


def _total(client, path, params) -> int:
    r = client.get(path, params={**params, "limit": 1})
    assert r.status_code == 200, f"{path} {params}: HTTP {r.status_code} {r.text[:200]}"
    return r.json()["total"]


def _witness_day(client, path, field, extra, max_pages=10):
    """The day of the first item on the route's own pages whose `field` carries a time
    of day, or None. A route whose recent items are all midnight cannot show the defect
    on page 1 (EPRS: the newest timed row is two months old), so keep paging. With no
    timed item at all the route still has to pass the invariant on any dated item."""
    first_dated = None
    for page in range(1, max_pages + 1):
        r = client.get(path, params={**extra, "limit": 50, "page": page})
        assert r.status_code == 200, f"{path}: HTTP {r.status_code} {r.text[:200]}"
        items = _items(r.json())
        dated = [i[field] for i in items if i.get(field)]
        timed = [v for v in dated if len(v) > 10 and v[11:19] != "00:00:00"]
        if timed:
            return date.fromisoformat(timed[0][:10]), True
        first_dated = first_dated or (dated[0] if dated else None)
        if len(items) < 50:
            break
    return (date.fromisoformat(first_dated[:10]), False) if first_dated else (None, False)


@pytest.mark.parametrize("path,lo,hi,field,extra", RANGE_CASES,
                         ids=[f"{c[0]}:{c[2]}" for c in RANGE_CASES])
def test_upper_bound_includes_the_whole_day(client, path, lo, hi, field, extra):
    d, timed = _witness_day(client, path, field, extra)
    if d is None:
        pytest.skip(f"{path} serves no dated item")
    nxt = d + timedelta(days=1)
    one = _total(client, path, {**extra, lo: d.isoformat(), hi: d.isoformat()})
    two = _total(client, path, {**extra, lo: nxt.isoformat(), hi: nxt.isoformat()})
    both = _total(client, path, {**extra, lo: d.isoformat(), hi: nxt.isoformat()})
    assert one >= 1, f"{path}: the witness is dated {d} but {lo}={hi}={d} returned nothing"
    assert one + two == both, (
        f"{path}: {d} alone {one} + {nxt} alone {two} != both days {both}"
        f"{' (witness has a time of day)' if timed else ''}")


def test_deadline_before_includes_the_whole_day(client):
    path = "/api/v2/funding/entrepreneur-instruments"
    d, _ = _witness_day(client, path, "deadline", {})
    if d is None:
        pytest.skip("no call with a deadline")
    on = _total(client, path, {"deadline_before": d.isoformat()})
    before = _total(client, path, {"deadline_before": (d - timedelta(days=1)).isoformat()})
    assert on > before, f"a call closes on {d}, yet deadline_before={d} ({on}) == the day before ({before})"


def test_a_far_future_bound_does_not_overflow(client):
    """`date + timedelta(days=1)` raises OverflowError on 9999-12-31, a value callers
    send to mean 'no upper bound'. The ORM filters use datetime.combine(d, time.max)."""
    for path, _lo, hi, _f, extra in RANGE_CASES:
        r = client.get(path, params={**extra, hi: "9999-12-31", "limit": 1})
        assert r.status_code == 200, f"{path} {hi}=9999-12-31: HTTP {r.status_code}"
