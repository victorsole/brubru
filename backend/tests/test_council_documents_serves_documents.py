"""/council-documents served a calendar (24 September 2026).

The endpoint unions the Council document corpus with Council MEETINGS, ordered by date.
Meetings are FUTURE-dated, so an endpoint called council-documents opened with next
month's summits and the register documents began below them. Measured before the fix:
the first page held 16 meetings and 34 documents, and every one of the top rows was a
meeting in October.

`source` now decides: `documents` (default), `meetings`, or `all`, which is the answer
the endpoint used to give.

The last test here is about a different kind of defect. The v2 routes are generated from
the v1 signatures and delegate by keyword; a parameter added to v1 and not regenerated is
not "missing" at the v2 edge, it arrives as FastAPI's `Query` object, and the branch that
reads it silently takes neither path. When that happened during this work, v2 answered
`total: 0` for every source while v1 was correct.
"""
from __future__ import annotations

import pathlib
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from main import app  # noqa: E402
from models.user import User  # noqa: E402

V1 = "/api/v1/council-documents"
V2 = "/api/v2/council/council-documents"


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(email="t@example.com", role="admin")
    yield TestClient(app)
    app.dependency_overrides.pop(api_user_with_rate_limit, None)


@pytest.mark.parametrize("path", [V1, V2])
def test_the_default_answer_is_documents_not_meetings(client, path):
    body = client.get(path, params={"limit": 25}).json()
    kinds = {r["source"] for r in body["data"]}
    assert kinds == {"publication"}, f"a calendar row reached the default answer: {kinds}"
    assert body["total"] > 0


@pytest.mark.parametrize("path", [V1, V2])
def test_meetings_are_still_available_on_request(client, path):
    body = client.get(path, params={"limit": 10, "source": "meetings"}).json()
    assert body["data"] and {r["source"] for r in body["data"]} == {"calendar_event"}


@pytest.mark.parametrize("path", [V1, V2])
def test_all_restores_the_old_answer(client, path):
    docs = client.get(path, params={"limit": 1, "source": "documents"}).json()["total"]
    meets = client.get(path, params={"limit": 1, "source": "meetings"}).json()["total"]
    both = client.get(path, params={"limit": 1, "source": "all"}).json()["total"]
    assert both == docs + meets


@pytest.mark.parametrize("path", [V1, V2])
def test_the_total_counts_only_what_the_caller_asked_for(client, path):
    """A total that counts meetings while the page holds documents sends a client paging
    for rows that are not there."""
    body = client.get(path, params={"limit": 5, "source": "documents"}).json()
    seen = 0
    for page in range(1, min(6, body["pages"]) + 1):
        rows = client.get(path, params={"limit": 5, "page": page, "source": "documents"}).json()["data"]
        assert all(r["source"] == "publication" for r in rows)
        seen += len(rows)
    assert seen > 0


def test_an_unknown_source_is_refused(client):
    assert client.get(V1, params={"source": "calendar"}).status_code == 422


def test_v2_asks_v1_for_the_same_thing(client):
    """v2 delegates by keyword, so a v1 parameter that was never regenerated arrives as a
    Query object and the reading branch takes neither path: v2 answered `total: 0` for
    every source during this work while v1 was right. Compare the two, every source."""
    for source in ("documents", "meetings", "all"):
        v1 = client.get(V1, params={"limit": 5, "source": source}).json()
        v2 = client.get(V2, params={"limit": 5, "source": source}).json()
        assert v1["total"] == v2["total"], f"v1 and v2 disagree on source={source}"
        assert [r["id"] for r in v1["data"]] == [r["id"] for r in v2["data"]]
