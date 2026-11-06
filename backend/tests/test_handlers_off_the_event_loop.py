"""O213 (6 Nov 2026): production runs ONE uvicorn process. A route handler declared `async def` that calls the
database synchronously runs that query on the event loop, so one slow filter or sort held every other request
(a 40 s `awards?order=oldest` timed out a small call elsewhere). Handlers that never await are plain `def` now:
FastAPI runs them in its thread pool and the loop stays free.

These tests use the REAL route factories and handlers; only the database work is replaced by a blocking sleep."""
import asyncio
import inspect
import time

import httpx
import pytest
from fastapi import APIRouter, FastAPI

BLOCK_S = 0.8


def _economy_app(monkeypatch):
    from api.v1 import _deps
    from api.v2 import economy_endpoints as eco
    from core.database import get_db

    def blocking_list(*a, **k):  # stands in for a minute-long query: it holds its thread, as psycopg2 does
        time.sleep(BLOCK_S)
        return [], 0

    monkeypatch.setattr(eco, "_list_items", blocking_list)
    router = APIRouter(prefix="/api/v2/esma")
    eco.register_resource(router, body_code="esma", item_type="financial_instrument", slug="financial-instruments",
                          noun="financial instruments", body_name="ESMA", acronym="ESMA", tag="t", source="s")
    app = FastAPI()
    app.include_router(router)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    app.dependency_overrides[_deps.api_user_with_rate_limit] = lambda: object()
    app.dependency_overrides[get_db] = lambda: None
    return app


async def _slow_and_ping(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        # Timed from the start: on a blocked loop even this sleep cannot wake until the list's query ends.
        t0 = time.perf_counter()
        slow = asyncio.create_task(c.get("/api/v2/esma/financial-instruments?order=title"))
        await asyncio.sleep(0.15)  # the slow list is now inside its query
        r = await c.get("/ping")
        ping_done_s = time.perf_counter() - t0
        return (await slow).status_code, r.status_code, ping_done_s


def test_a_slow_list_no_longer_holds_the_other_requests(monkeypatch):
    slow_status, ping_status, ping_done_s = asyncio.run(_slow_and_ping(_economy_app(monkeypatch)))
    assert (slow_status, ping_status) == (200, 200)
    assert ping_done_s < BLOCK_S * 0.75, f"/ping answered {ping_done_s:.2f} s in, behind a blocking list: the handler runs on the loop"


def test_the_factory_handlers_and_the_o213_lists_are_plain_functions():
    from api.v2 import economy_endpoints as eco
    from api.v2.funding import awards, eu_funding_recipients
    router = APIRouter()
    eco.register_resource(router, body_code="x", item_type="y", slug="z", noun="n", body_name="B", acronym="B",
                          tag="t", source="s", procurement=True, documents=True)
    eco.register_resource(router, body_code="x", item_type="w", slug="w", noun="n", body_name="B", acronym="B",
                          tag="t", source="s", funding_standard=True)
    endpoints = {r.path: r.endpoint for r in router.routes}
    assert len(endpoints) >= 6
    for path, ep in endpoints.items():
        assert not inspect.iscoroutinefunction(ep), f"{path} is async again: its query would run on the event loop"
    for ep in (awards.list_awards, eu_funding_recipients.list_recipients):
        assert not inspect.iscoroutinefunction(ep), ep.__name__


def test_no_handler_that_another_module_awaits_was_made_plain():
    # api/v2/advisory_opinions awaits these v1 handlers through router.routes[...].endpoint: they must stay async
    # until that caller changes, or every v2 opinions call fails with "object can't be used in 'await'".
    from api.v1 import advisory_opinions as v1
    for r in v1.router.routes:
        if r.path.startswith("/advisory-opinions"):
            assert inspect.iscoroutinefunction(r.endpoint), r.path
