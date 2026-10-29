"""The EU Funding & Tenders Portal's news and events in the News and Events folders (funding standard
Phase 3, 29 Oct 2026; proposal of 23 Oct 2026 §2): /news/ft-portal and /events/ft-portal are the
aggregators with body=ftportal, every argument passed; /funding/ft-news and /funding/ft-events stay,
marked legacy."""
from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1._envelope import build_envelope


def _app(router, prefix):
    from api.v1._deps import api_user_with_rate_limit
    from core.database import get_db
    app = FastAPI()
    app.include_router(router, prefix=prefix)
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    return TestClient(app)


def test_the_portal_news_route_is_news_all_with_its_body_and_every_argument(monkeypatch):
    import inspect
    import api.v2.news as N
    real = N.list_news
    got = {}

    async def fake_list_news(**kw):
        got.update(kw)
        return build_envelope([], 0, 1, 20)
    monkeypatch.setattr(N, "list_news", fake_list_news)
    r = _app(N.router, "/api/v2").get("/api/v2/news/ft-portal", params={
        "kind": "news", "from": "2026-01-02", "to": "2026-10-27", "days": 9, "q": "info day",
        "updated_from": "2026-10-01T00:00:00", "updated_to": "2026-10-28", "order": "oldest", "page": 3,
        "limit": 7, "include_body": "false"})
    assert r.status_code == 200, r.text
    assert (got["body"], got["family"]) == ("ftportal", None)
    assert (got["kind"], got["from_"], got["to"], got["days"], got["q"]) == ("news", date(2026, 1, 2), date(2026, 10, 27), 9, "info day")
    assert got["updated_from"] == datetime(2026, 10, 1) and got["updated_to"] is not None
    assert (got["order"], got["page"], got["limit"], got["include_body"]) == ("oldest", 3, 7, False)
    # nothing left to its Query default: every parameter of list_news is passed
    assert set(inspect.signature(real).parameters) == set(got)


def test_the_portal_events_route_is_events_all_with_its_body_and_every_argument(monkeypatch):
    import inspect
    import api.v2.events as E
    real = E.list_events
    got = {}

    async def fake_list_events(**kw):
        got.update(kw)
        return build_envelope([], 0, 1, 20)
    monkeypatch.setattr(E, "list_events", fake_list_events)
    r = _app(E.router, "/api/v2").get("/api/v2/events/ft-portal", params={
        "when": "upcoming", "from": "2026-11-01", "to": "2026-12-31", "days": 30, "q": "info day",
        "source": "calendar", "include_body": "false", "order": "soonest", "page": 2, "limit": 9})
    assert r.status_code == 200, r.text
    assert (got["body"], got["family"]) == ("ftportal", None)
    assert (got["when"], got["from_"], got["to"], got["days"], got["q"], got["source"]) == (
        "upcoming", date(2026, 11, 1), date(2026, 12, 31), 30, "info day", "calendar")
    assert (got["include_body"], got["order"], got["page"], got["limit"]) == (False, "soonest", 2, 9)
    assert set(inspect.signature(real).parameters) == set(got)


def test_the_new_routes_come_before_the_item_routes_and_the_old_ones_are_legacy():
    from api.v2.funding import router as funding
    from api.v2.news import router as news
    from api.v2.events import router as events
    for router, path, item in ((news, "/news/ft-portal", "/news/{item_id}"), (events, "/events/ft-portal", "/events/{event_id}")):
        paths = [r.path for r in router.routes]
        assert paths.index(path) < paths.index(item), path
    app = FastAPI()
    app.include_router(funding, prefix="/api/v2")
    spec = app.openapi()["paths"]
    deprecated = sorted(p for p, ops in spec.items() if ops.get("get", {}).get("deprecated"))
    # funding-opportunities has been the legacy alias of ft-calls-for-proposals since Phase 0
    assert deprecated == ["/api/v2/funding/ft-events", "/api/v2/funding/ft-events/{item_id}",
                          "/api/v2/funding/ft-news", "/api/v2/funding/ft-news/{item_id}",
                          "/api/v2/funding/funding-opportunities", "/api/v2/funding/funding-opportunities/{topic_id}"]
    assert "/api/v2/news/ft-portal" in spec["/api/v2/funding/ft-news"]["get"]["description"]
    assert "/api/v2/events/ft-portal" in spec["/api/v2/funding/ft-events"]["get"]["description"]
