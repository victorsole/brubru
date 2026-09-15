"""`updated_to=YYYY-MM-DD` covers that whole day.

A bare date parsed as MIDNIGHT at the start of the day, so an incremental sync asking
"up to 15 September" lost every row updated during the 15th (15 Sep 2026). Checked
through the routes: for a day d on which rows were updated,
count(updated d..d) + count(updated d+1..d+1) == count(updated d..d+1).
"""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from api.v1._date_bounds import _end_of_day_if_bare_date
from api.v1._deps import api_user_with_rate_limit
from main import app
from models.user import User

ROUTES = ["/api/v1/laws", "/api/v1/calendar/events", "/api/v1/procedures",
          "/api/v1/eprs", "/api/v1/resolutions"]


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(email="test@example.com", role="admin")
    yield TestClient(app)
    app.dependency_overrides.pop(api_user_with_rate_limit, None)


def test_a_bare_date_becomes_the_end_of_that_day_and_a_datetime_is_untouched():
    assert _end_of_day_if_bare_date("2026-09-15").isoformat() == "2026-09-15T23:59:59.999999"
    assert _end_of_day_if_bare_date("2026-09-15T10:00:00") == "2026-09-15T10:00:00"


def _total(client, path, params):
    r = client.get(path, params={**params, "limit": 1})
    assert r.status_code == 200, f"{path} {params}: {r.status_code} {r.text[:200]}"
    return r.json()["total"]


def _witness_day(client, path):
    """A recent day on which the route has rows updated, found through the route
    itself: total(updated_from=d) > total(updated_from=d+1)."""
    today = date.today()
    for back in range(0, 15):
        d = today - timedelta(days=back)
        if _total(client, path, {"updated_from": d.isoformat()}) > _total(
                client, path, {"updated_from": (d + timedelta(days=1)).isoformat()}):
            return d
    return None


@pytest.mark.parametrize("path", ROUTES)
def test_updated_to_includes_the_whole_day(client, path):
    d = _witness_day(client, path)
    if d is None:
        pytest.skip(f"{path}: nothing updated in the last 15 days")
    n = d + timedelta(days=1)
    one = _total(client, path, {"updated_from": d.isoformat(), "updated_to": d.isoformat()})
    two = _total(client, path, {"updated_from": n.isoformat(), "updated_to": n.isoformat()})
    both = _total(client, path, {"updated_from": d.isoformat(), "updated_to": n.isoformat()})
    assert one >= 1, f"{path}: rows were updated on {d} but updated_from=updated_to={d} returned none"
    assert one + two == both, f"{path}: {one} + {two} != {both}"
