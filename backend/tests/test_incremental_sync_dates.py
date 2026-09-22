"""Created / updated dates and filters for incremental sync (22 Sep 2026).

A partner (GovClipping) syncs the API every morning and reported that six list endpoints
had no usable date and no date filter, so finding what changed meant re-reading every
page: MEPs, commissioners, EU officials, infringements, calls for proposals, calls for
tenders. It also asked for pages of 100 rather than 25.

Tested here:
  * the window contract (UTC, whole-day upper bound, inverted window = 422, sync orders);
  * the trigger of migration 234 against the live tables, inside a rolled-back
    transaction: a sync that rewrites the same content must NOT move the date, a real
    change must, and the created column can never move;
  * the snapshot store for records that are not rows (MEPs, commissioners);
  * each of the six v2 endpoints: dates on every item, the filters narrowing to what
    the table says, page sizes up to 500;
  * MEPs: sitting MEPs by default (719, not the 744 who have sat this term), former
    members with an updated_ window, name search accent-insensitive, and no per-MEP
    profile call when the snapshot has the record (the EP API rate-limits them).
"""
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from api.v1 import _change_window as cw  # noqa: E402
from api.v1 import meps as meps_v1  # noqa: E402
from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from core.database import SessionLocal  # noqa: E402
from main import app  # noqa: E402
from models.user import User  # noqa: E402
from services import api_snapshots  # noqa: E402

UTC = timezone.utc

SIX = {
    "meps": "/api/v2/parliament/meps",
    "commissioners": "/api/v2/commission/commissioners",
    "officials": "/api/v2/who-is-who/officials",
    "infringements": "/api/v2/commission/infringements",
    "calls_for_proposals": "/api/v2/funding/ft-calls-for-proposals",
    "calls_for_tenders": "/api/v2/funding/ft-calls-for-tenders",
}
TABLE_LISTS = {  # path -> (table, created column, updated column)
    "/api/v2/who-is-who/officials": ("who_is_who_officials", "first_seen", "content_updated_at"),
    "/api/v2/commission/infringements": ("infringement_cases", "creation_date", "content_updated_at"),
    "/api/v2/commission/infringements/decisions": ("infringement_decisions", "creation_date", "content_updated_at"),
    "/api/v2/funding/ft-calls-for-proposals": ("ft_calls_for_proposals", "first_seen_at", "content_updated_at"),
    "/api/v2/funding/ft-calls-for-tenders": ("ft_calls_for_tenders", "first_seen_at", "content_updated_at"),
}


# --------------------------------------------------------------------------- the window contract
def test_a_naive_datetime_is_utc_and_an_aware_one_is_converted():
    assert cw.utc(datetime(2026, 9, 21, 7, 0)) == datetime(2026, 9, 21, 7, 0, tzinfo=UTC)
    cet = timezone(timedelta(hours=2))
    assert cw.utc(datetime(2026, 9, 21, 9, 0, tzinfo=cet)) == datetime(2026, 9, 21, 7, 0, tzinfo=UTC)


def test_an_inverted_window_is_a_422_naming_the_bounds():
    with pytest.raises(HTTPException) as e:
        cw.validate_window(updated_from=datetime(2026, 9, 22), updated_to=datetime(2026, 9, 21))
    assert e.value.status_code == 422 and "updated_from" in e.value.detail["message"]


def test_sync_orders_break_ties_on_id():
    assert cw.sql_order("updated_asc", "c", "u") == "u ASC, id ASC"
    assert cw.sql_order("created_desc", "c", "u", "d.id") == "c DESC, d.id DESC"
    assert cw.sql_order("recent", "c", "u") is None


# --------------------------------------------------------------------------- the trigger (rolled back)
@pytest.fixture()
def tx():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.mark.parametrize("table,created,touch,content", [
    ("ft_calls_for_proposals", "first_seen_at", "scraped_at = now(), last_updated = now()", "title = title || ' x'"),
    ("ft_calls_for_tenders", "first_seen_at", "scraped_at = now(), last_updated = now()", "title = title || ' x'"),
    ("who_is_who_officials", "first_seen", "fetched_at = now()", "position = coalesce(position, '') || ' x'"),
    ("infringement_cases", "creation_date", "last_seen_at = now()", "title = title || ' x'"),
    ("infringement_decisions", "creation_date", "last_seen_at = now()", "title = title || ' x'"),
])
def test_only_a_content_change_moves_the_updated_date(tx, table, created, touch, content):
    row = tx.execute(text(f"SELECT id, {created} AS c, content_updated_at AS u FROM {table} "
                          f"ORDER BY content_updated_at LIMIT 1")).one()
    # A sync that sees the same content: bookkeeping moves, the change date does not,
    # and neither does the created date, even when a writer tries to set it.
    tx.execute(text(f"UPDATE {table} SET {touch}, {created} = now() + interval '1 day' WHERE id = :id"), {"id": row.id})
    after = tx.execute(text(f"SELECT {created} AS c, content_updated_at AS u FROM {table} WHERE id = :id"), {"id": row.id}).one()
    assert (after.c, after.u) == (row.c, row.u)
    # A real change moves it.
    tx.execute(text(f"UPDATE {table} SET {content} WHERE id = :id"), {"id": row.id})
    moved = tx.execute(text(f"SELECT content_updated_at AS u FROM {table} WHERE id = :id"), {"id": row.id}).scalar()
    assert moved > row.u


# --------------------------------------------------------------------------- the snapshot store
def test_the_snapshot_moves_the_date_only_on_a_new_hash_and_guards_removals(tx):
    ds = "test_incremental_sync"
    first = api_snapshots.record(tx, ds, {"a": {"v": 1}, "b": {"v": 1}}, complete=True)
    assert first["new"] == 2
    d0 = api_snapshots.dates_for(tx, ds)
    again = api_snapshots.record(tx, ds, {"a": {"v": 1}, "b": {"v": 2}}, complete=True)
    assert (again["unchanged"], again["changed"]) == (1, 1)
    # now() is the transaction time, so a same-transaction change keeps the value;
    # what matters is that the unchanged record kept its hash row untouched.
    assert api_snapshots.dates_for(tx, ds)["a"] == d0["a"]
    # Dropping 1 of 2 is 50%: a partial fetch, refused.
    with pytest.raises(RuntimeError):
        api_snapshots.record(tx, ds, {"a": {"v": 1}}, complete=True)


def test_a_flaky_field_keeps_its_known_value(tx):
    ds = "test_incremental_sync_keep"
    api_snapshots.record(tx, ds, {"m": {"country": "ESP", "name": "X"}}, complete=False, keep_known=("country",))
    counts = api_snapshots.record(tx, ds, {"m": {"country": None, "name": "X"}}, complete=False, keep_known=("country",))
    assert counts["unchanged"] == 1
    assert api_snapshots.payloads_for(tx, ds)["m"]["country"] == "ESP"


# --------------------------------------------------------------------------- the six endpoints
@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(email="test@example.com", role="admin")
    yield TestClient(app)
    app.dependency_overrides.pop(api_user_with_rate_limit, None)


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.mark.parametrize("path", [p for k, p in SIX.items() if k != "meps"])
def test_every_item_carries_both_dates(client, path):
    r = client.get(path)
    assert r.status_code == 200, r.text
    items = r.json()["data"]
    assert items
    for it in items:
        assert "creation_date" in it and "updated_date" in it
    assert sum(1 for it in items if it["creation_date"] and it["updated_date"]) == len(items)


@pytest.mark.parametrize("path", [p for k, p in SIX.items() if k not in ("meps", "commissioners")])
def test_pages_go_to_500_and_default_to_100(client, path):
    assert len(client.get(path, params={"limit": 500}).json()["data"]) == 500
    assert client.get(path).json()["limit"] == 100
    assert client.get(path, params={"limit": 501}).status_code == 422


@pytest.mark.parametrize("path,spec", list(TABLE_LISTS.items()))
def test_the_updated_window_returns_exactly_what_the_table_says(client, db, path, spec):
    table, created, updated = spec
    # A window around a real change date, so the answer is small and non-zero.
    pivot = db.execute(text(f"SELECT {updated} FROM {table} ORDER BY {updated} DESC OFFSET 3 LIMIT 1")).scalar()
    extra = " AND removed_at IS NULL" if table == "who_is_who_officials" else ""
    extra = "" if table == "who_is_who_officials" else extra  # an updated_ window includes departures
    extra += " AND NOT is_test" if table.startswith("ft_") else ""
    expected = db.execute(text(f"SELECT count(*) FROM {table} WHERE {updated} >= :p{extra}"), {"p": pivot}).scalar()
    r = client.get(path, params={"updated_from": pivot.isoformat(), "order": "updated_asc", "limit": 500})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == expected > 0
    stamps = [it["updated_date"] for it in body["data"]]
    assert stamps == sorted(stamps)
    assert all(datetime.fromisoformat(s) >= pivot for s in stamps)


@pytest.mark.parametrize("path", list(TABLE_LISTS))
def test_created_window_and_inverted_window(client, path):
    future = (datetime.now(UTC) + timedelta(days=2)).date().isoformat()
    assert client.get(path, params={"created_from": future}).json()["total"] == 0
    assert client.get(path, params={"updated_from": "2026-09-22", "updated_to": "2026-09-21"}).status_code == 422


def test_a_bare_date_upper_bound_covers_the_whole_day(client, db):
    day = db.execute(text("SELECT max(content_updated_at)::date FROM infringement_cases")).scalar()
    n = db.execute(text("SELECT count(*) FROM infringement_cases WHERE content_updated_at::date = :d"), {"d": day}).scalar()
    r = client.get(SIX["infringements"], params={"updated_from": day.isoformat(), "updated_to": day.isoformat()})
    assert r.json()["total"] == n > 0


def test_officials_hide_departures_unless_a_sync_asks(client, db):
    gone = db.execute(text("SELECT count(*) FROM who_is_who_officials WHERE removed_at IS NOT NULL")).scalar()
    listed = db.execute(text("SELECT count(*) FROM who_is_who_officials WHERE removed_at IS NULL")).scalar()
    assert client.get(SIX["officials"]).json()["total"] == listed
    assert client.get(SIX["officials"], params={"include_removed": "true"}).json()["total"] == listed + gone


def test_commissioners_answer_a_window(client):
    assert client.get(SIX["commissioners"], params={"updated_from": "2099-01-01"}).json()["total"] == 0
    everyone = client.get(SIX["commissioners"], params={"updated_from": "2000-01-01"}).json()
    assert everyone["total"] >= 27 and all(it["updated_date"] for it in everyone["data"])


# --------------------------------------------------------------------------- MEPs (no EP calls)
def _raw(i, name):
    return {"identifier": str(i), "label": name}


@pytest.fixture()
def fake_ep(monkeypatch):
    """The EP list: 3 MEPs this term, one of whom has left. No network."""
    raw = [_raw(1, "Víctor SOLÉ"), _raw(2, "Anna SMITH"), _raw(3, "Left EARLY")]

    async def fake_all(country=None, group=None, term=10, patient=False):
        return raw

    async def fake_current(patient=False):
        return {"1", "2"}

    calls = []

    async def fake_profile(mep_id, patient=False):
        calls.append(mep_id)
        return None

    monkeypatch.setattr(meps_v1, "_fetch_all", fake_all)
    monkeypatch.setattr(meps_v1, "_fetch_current_ids", fake_current)
    monkeypatch.setattr(meps_v1, "_fetch_profile", fake_profile)
    now = datetime.now(UTC)
    snap = {k: meps_v1.MEPItem(id=k, full_name=n, country="ESP", group="org/7018").model_dump(mode="json",
                                                                                          exclude={"creation_date", "updated_date"})
            for k, n in (("1", "Víctor SOLÉ"), ("2", "Anna SMITH"), ("3", "Left EARLY"))}
    dates = {"1": (now - timedelta(days=90), now - timedelta(days=90), None),
             "2": (now - timedelta(days=90), now - timedelta(hours=2), None),
             "3": (now - timedelta(days=90), now - timedelta(hours=1), None)}
    monkeypatch.setattr(api_snapshots, "payloads_for", lambda db, ds: snap)
    monkeypatch.setattr(api_snapshots, "dates_for", lambda db, ds, keys=None: {
        k: v for k, v in dates.items() if keys is None or k in set(keys)})
    return calls


def test_meps_default_to_those_sitting_today(client, fake_ep):
    body = client.get(SIX["meps"]).json()
    assert body["total"] == 2 and {m["id"] for m in body["data"]} == {"1", "2"}
    assert all(m["in_office"] and m["country"] == "ESP" for m in body["data"])
    assert fake_ep == []  # served from the snapshot: no per-MEP profile call


def test_former_meps_on_request_and_in_an_updated_window(client, fake_ep):
    assert client.get(SIX["meps"], params={"include_former": "true"}).json()["total"] == 3
    since = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    body = client.get(SIX["meps"], params={"updated_from": since, "order": "updated_asc"}).json()
    assert [m["id"] for m in body["data"]] == ["2", "3"]
    assert body["data"][1]["in_office"] is False


def test_mep_name_search_ignores_accents_and_case(client, fake_ep):
    body = client.get(SIX["meps"], params={"name": "sole"}).json()
    assert [m["id"] for m in body["data"]] == ["1"]


def test_mep_dates_are_for_the_current_term_only(client, fake_ep):
    assert client.get(SIX["meps"], params={"term": 9, "updated_from": "2026-01-01"}).status_code == 422
