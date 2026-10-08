"""One row, one stable id, per Commission Transparency Register meeting (8 Oct 2026).

GovClipping found it: "BruBru gives each transparency meeting a new UUID on every reload".
The ingest minted uuid4() per row and inserted with a bare ON CONFLICT DO NOTHING, but the
only unique key was that random id, so every scheduled run re-inserted every meeting:
475,782 rows for 30,155 meetings. Migration 283 keyed the table on the register row's
content (meeting_key) and kept the oldest copy of each.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.v1._deps import api_user_with_rate_limit
from main import app
from models.user import User

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def db():
    from core.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(email="test@example.com", role="admin")
    yield TestClient(app)
    app.dependency_overrides.pop(api_user_with_rate_limit, None)


def test_one_row_per_meeting(db):
    rows, keys = db.execute(text(
        "SELECT count(*), count(DISTINCT meeting_key) FROM transparency_meetings")).one()
    assert rows == keys, f"{rows - keys} duplicate meeting row(s)"


def test_the_meeting_key_is_enforced_unique(db):
    """Without a unique key, ON CONFLICT DO NOTHING never fires: the original bug."""
    n = db.execute(text("""
        SELECT count(*) FROM pg_indexes
        WHERE tablename = 'transparency_meetings' AND indexname = 'ux_transparency_meetings_meeting_key'
          AND indexdef ILIKE '%UNIQUE%'
    """)).scalar()
    assert n == 1, "the unique index on meeting_key is missing"


def test_the_api_never_serves_the_same_meeting_twice(client):
    items = client.get("/api/v2/commission/meetings", params={"limit": 100}).json()["data"]
    assert items
    seen = {}
    for i in items:
        k = (i["host_uuid"], i["host_name"], i["meeting_date"], i["organisation_met"], i["subject"],
             i.get("location"), str(i.get("representatives")))
        assert k not in seen, f"same meeting served as {seen[k]} and {i['id']}"
        seen[k] = i["id"]
